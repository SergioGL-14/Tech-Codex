#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sections/news_section.py  ·  Noticias RSS
Re-factoring integral 25-abr-2025
"""
from __future__ import annotations

import html
import logging
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Final, Iterable, List, Sequence

import feedparser
import sqlite3
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, QDate, QUrl
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from utils import DB_PATH, clear_layout, get_conn  # ← utilidades comunes

_LOG = logging.getLogger(__name__)
_LOG.setLevel(logging.INFO)

# ╔═══════════════════════════  Config  ════════════════════════════╗
@dataclass(slots=True, frozen=True)
class NewsCfg:
    DB_FILE:   Path = DB_PATH
    LIMIT:     int  = 50                # nº noticias que se conservan (salvo fav)
    INTERVAL:  int  = 10                # minutos entre recargas automáticas
    RETRIES:   int  = 3                 # intentos por feed
    FEEDS: Sequence[tuple[str, str]] = (
        ("Genbeta",           "https://www.genbeta.com/rss"),
        ("MuyComputer",       "https://www.muycomputer.com/feed"),
        ("El Androide Libre", "https://elandroidelibre.elespanol.com/feed"),
        ("DesdeLinux",        "https://desdelinux.net/feed/"),
        ("Linux Adictos",     "https://linuxadictos.com/feed/"),
        ("El Atareao",        "https://elatareao.com/feed/"),
        ("MuyLinux",          "https://www.muylinux.com/feed/"),
    )

CFG: Final = NewsCfg()

# ╔═══════════════════════  BD helpers  ════════════════════════════╗
import sqlite3
from typing import Sequence
from utils import get_conn, clear_layout

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS noticias(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente        TEXT NOT NULL,
    titulo        TEXT NOT NULL,
    link          TEXT NOT NULL,
    resumen       TEXT,
    fecha_pub     TEXT NOT NULL,
    fecha_entrada TEXT NOT NULL,
    leido         INTEGER DEFAULT 0,
    favorito      INTEGER DEFAULT 0,
    UNIQUE(fuente, titulo)
);
"""

def _ensure_db() -> None:
    # Usa get_conn() para tener row_factory y WAL ya configurados
    with get_conn() as c:
        c.executescript(_CREATE_SQL)

_ensure_db()

def db_exec(sql: str, params: Sequence = ()) -> None:
    """Ejecuta INSERT/UPDATE/DELETE en el mismo techcodex.db"""
    with get_conn() as c:
        c.execute(sql, params)
        c.commit()

def db_fetch(sql: str, params: Sequence = ()) -> list[sqlite3.Row]:
    """
    Ejecuta un SELECT y devuelve una lista de sqlite3.Row,
    de modo que puedes hacer r['fecha_pub'] sin problemas.
    """
    with get_conn() as c:
        return c.execute(sql, params).fetchall()

# ╔══════════════════════  RSS Fetcher  ════════════════════════════╗
class RSSFetcher(QThread):
    finished = pyqtSignal(int)          # nº de nuevas noticias

    def __init__(self, feeds: Iterable[tuple[str, str]]) -> None:
        super().__init__()
        self.feeds = list(feeds)

    def run(self) -> None:  # noqa: D401
        now_iso = datetime.now(timezone.utc).isoformat()
        rows: list[tuple] = []

        for alias, url in self.feeds:
            feed = self._retry_parse(url)
            if not feed or (feed.bozo and not feed.entries):
                continue
            for entry in feed.entries:
                titulo = entry.get("title", "").strip()
                link   = entry.get("link",  "").strip()
                if not titulo or not link:
                    continue
                resumen_raw = (
                    entry.get("summary") or entry.get("description") or ""
                )
                resumen = html.unescape(resumen_raw.strip())
                struct  = entry.get("published_parsed") or entry.get("updated_parsed")
                fecha_pub = (
                    datetime(*struct[:6], tzinfo=timezone.utc).isoformat()
                    if struct else now_iso
                )
                rows.append((alias, titulo, link, resumen, fecha_pub, now_iso))

        inserted = self._insert_batch(rows)
        self.finished.emit(inserted)

    # ---------- helpers ---------- #
    def _retry_parse(self, url: str):
        for n in range(1, CFG.RETRIES + 1):
            feed = feedparser.parse(url)
            if feed.entries or not feed.bozo:
                return feed
            if n < CFG.RETRIES:
                time.sleep(2)

    def _insert_batch(self, rows: List[tuple]) -> int:
        if not rows:
            return 0
        with get_conn() as c:
            cur = c.cursor()
            cur.executemany(
                """
                INSERT OR IGNORE INTO noticias
                  (fuente,titulo,link,resumen,fecha_pub,fecha_entrada)
                VALUES(?,?,?,?,?,?)
                """,
                rows,
            )
            cur.execute(
                """
                DELETE FROM noticias
                 WHERE favorito=0
                   AND id NOT IN (
                       SELECT id FROM noticias
                        WHERE favorito=0
                        ORDER BY fecha_entrada DESC
                        LIMIT ?
                   )
                """,
                (CFG.LIMIT,),
            )
            c.commit()
            return cur.rowcount

# ╔══════════════════════  Card UI  ════════════════════════════════╗
class NewsCard(QGroupBox):
    def __init__(self, row: sqlite3.Row, parent: QWidget | None = None):
        super().__init__(parent)
        # guardamos estado en atributos mutables
        self.news_id = row["id"]
        self._leido  = bool(row["leido"])
        self._fav    = bool(row["favorito"])

        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        v = QVBoxLayout(self)

        ttl = QLabel(f"📰 {row['titulo']}")
        ttl.setWordWrap(True)
        ttl.setStyleSheet("font-weight:bold;font-size:15px;")
        v.addWidget(ttl)

        meta = QLabel(f"{row['fuente']} · {row['fecha_pub'][:10]}")
        meta.setStyleSheet("color:#666;font-size:11px;")
        v.addWidget(meta)

        if row["resumen"]:
            doc = QTextDocument()
            doc.setHtml(row["resumen"])
            plain = doc.toPlainText().strip()
            snippet = plain[:280] + ("…" if len(plain) > 280 else "")
            lbl = QLabel(snippet)
            lbl.setWordWrap(True)
            v.addWidget(lbl)

        # --- botones ---
        h = QHBoxLayout()
        # Ver embebido
        b_view = QPushButton("🔍 Ver")
        b_view.clicked.connect(self._view)
        h.addWidget(b_view)
        # Abrir en navegador
        b_web = QPushButton("🌐 Navegador")
        b_web.clicked.connect(lambda: webbrowser.open(row["link"]))
        h.addWidget(b_web)
        # Lectura toggle
        self.btn_read = QPushButton("✔️ Leída" if self._leido else "❌ Leída")
        self.btn_read.clicked.connect(self._toggle_read)
        h.addWidget(self.btn_read)
        # Favorito toggle
        self.btn_fav = QPushButton("⭐ Favorito" if self._fav else "★ Marcar")
        self.btn_fav.clicked.connect(self._toggle_fav)
        h.addWidget(self.btn_fav)

        v.addLayout(h)

    # ---------- slots ---------- #
    def _toggle_read(self) -> None:
        self._leido = not self._leido
        db_exec("UPDATE noticias SET leido=? WHERE id=?", (int(self._leido), self.news_id))
        self.btn_read.setText("✔️ Leída" if self._leido else "❌ Leída")

    def _toggle_fav(self) -> None:
        self._fav = not self._fav
        db_exec("UPDATE noticias SET favorito=? WHERE id=?", (int(self._fav), self.news_id))
        self.btn_fav.setText("⭐ Favorito" if self._fav else "★ Marcar")

    def _view(self) -> None:
        if not self._leido:
            self._toggle_read()
        dlg = _BrowserDialog(self.news_id, parent=self)
        dlg.exec()

class _BrowserDialog(QDialog):
    """Visor embebido con QWebEngineView."""
    def __init__(self, news_id: int, parent: QWidget | None = None):
        # recargamos la fila para obtener el link y el título
        row = db_fetch("SELECT titulo, link FROM noticias WHERE id=?", (news_id,))[0]
        super().__init__(parent)
        self.setWindowTitle(row["titulo"])
        self.resize(1000, 700)

        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(f"<b>{row['titulo']}</b>"))
        top.addStretch()
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        top.addWidget(close)
        v.addLayout(top)

        web = QWebEngineView()
        web.load(QUrl(row["link"]))
        v.addWidget(web, 1)

# ╔══════════════════════  Widget principal  ════════════════════════╗
class NewsSection(QWidget):
    def __init__(self):
        super().__init__()
        self._fetcher: RSSFetcher | None = None

        root = QVBoxLayout(self)

        # --- filtros ---
        f = QHBoxLayout()
        self.cmb_src = QComboBox(); self.cmb_src.addItem("Todas", None)
        for n, _ in CFG.FEEDS: 
            self.cmb_src.addItem(n, n)
        self.txt    = QLineEdit(placeholderText="Buscar…")
        self.d_from = QDateEdit(); self.d_from.setDate(QDate.currentDate().addMonths(-1))
        self.d_to   = QDateEdit(); self.d_to.setDate(QDate.currentDate())
        self.chk_fav = QCheckBox("Sólo favoritos")
        for w,l in (
            (self.cmb_src,"Fuente:"),(self.txt,"Texto:"),
            (self.d_from,"Desde:"),(self.d_to,"Hasta:")
        ):
            f.addWidget(QLabel(l)); f.addWidget(w)
        f.addWidget(self.chk_fav); f.addStretch()
        today = QPushButton("Hoy"); today.clicked.connect(self._filter_today)
        f.addWidget(today)
        root.addLayout(f)

        # --- cabecera + recarga ---
        h = QHBoxLayout()
        h.addWidget(QLabel("<b>📰 Noticias</b>")); h.addStretch()
        self.btn_reload = QPushButton("🔄 Recargar")
        self.btn_reload.clicked.connect(self._manual_reload)
        h.addWidget(self.btn_reload)
        root.addLayout(h)

        # --- contenedor cards ---
        self.scroll = QScrollArea(widgetResizable=True)
        self.inner  = QWidget()
        self.cards  = QVBoxLayout(self.inner)
        self.cards.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.inner)
        root.addWidget(self.scroll, 1)

        # señales filtros
        for sig in (
            self.cmb_src.currentIndexChanged,
            self.txt.textChanged,
            self.d_from.dateChanged,
            self.d_to.dateChanged,
            self.chk_fav.stateChanged
        ):
            sig.connect(self._populate)

        self._populate()

        # timer auto-reload
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._auto_reload)
        self.timer.start(CFG.INTERVAL * 60 * 1000)

    # ---------- populate ---------- #
    def _filter_today(self) -> None:
        today = QDate.currentDate()
        self.d_from.setDate(today)
        self.d_to.setDate(today)

    def _populate(self) -> None:
        clear_layout(self.cards)
        rows = db_fetch("SELECT * FROM noticias ORDER BY fecha_entrada DESC")

        src = self.cmb_src.currentData()
        txt = self.txt.text().lower()
        d1  = self.d_from.date().toPyDate()
        d2  = self.d_to.date().toPyDate()
        fav = self.chk_fav.isChecked()

        for r in rows:
            pub = datetime.fromisoformat(r["fecha_pub"]).date()
            if src and r["fuente"] != src: continue
            if txt and txt not in (r["titulo"] + (r["resumen"] or "")).lower(): continue
            if not (d1 <= pub <= d2): continue
            if fav and not r["favorito"]: continue
            self.cards.addWidget(NewsCard(r, self))

    # ---------- recarga ---------- #
    def _manual_reload(self) -> None:
        if self._fetcher: return
        self._start_fetch()

    def _auto_reload(self) -> None:
        if not self._fetcher:
            self._start_fetch()

    def _start_fetch(self) -> None:
        self.btn_reload.setEnabled(False)
        self._fetcher = RSSFetcher(CFG.FEEDS)
        self._fetcher.finished.connect(self._on_fetch_done)
        self._fetcher.start()

    def _on_fetch_done(self, inserted: int) -> None:
        self._fetcher = None
        self.btn_reload.setEnabled(True)
        if inserted:
            self._populate()
            QMessageBox.information(
                self, "Noticias",
                f"{inserted} noticias nuevas ✔️"
            )

# ╔══════════════════════  Launcher demo  ══════════════════════════╗
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    w = NewsSection()
    w.resize(1000, 720)
    w.show()
    sys.exit(app.exec())