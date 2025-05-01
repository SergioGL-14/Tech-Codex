#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TipsSection — Consejo del Día con filtros, favoritos y botones globales.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton,
    QHBoxLayout, QMessageBox, QGroupBox, QScrollArea,
    QLabel, QSizePolicy, QComboBox, QLineEdit, QFrame,
)

from utils import clear_layout


class TipsSection(QWidget):
    """Consejo del Día – filtros arriba, tarjeta con metadatos y botones globales abajo."""

    def __init__(self, db_path: Path):
        super().__init__()
        self._db_path = db_path
        self._showing_favs = False
        self._current_tip: Optional[sqlite3.Row] = None

        # ——— LAYOUT EXTERIOR ———————————————————————————
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ───────────── Barra de filtros ──────────────
        filt_bar = QHBoxLayout()
        self.cmb_cat = QComboBox()
        self.cmb_level = QComboBox()
        self.txt_search = QLineEdit(placeholderText="Buscar texto…")
        btn_reset = QPushButton("Vista Predeterminada")
        btn_reset.clicked.connect(self._reset_filters)

        self.cmb_cat.addItem("Todas")
        self.cmb_level.addItem("Todos")
        self._populate_filter_values()

        for w, lbl in (
            (self.cmb_cat, "Categoría:"),
            (self.cmb_level, "Nivel:"),
            (self.txt_search, "Texto:"),
        ):
            filt_bar.addWidget(QLabel(lbl))
            filt_bar.addWidget(w)
        filt_bar.addWidget(btn_reset)
        filt_bar.addStretch()
        root.addLayout(filt_bar)

        # Eventos filtros
        self.cmb_cat.currentIndexChanged.connect(self._apply_filters)
        self.cmb_level.currentIndexChanged.connect(self._apply_filters)
        self.txt_search.textChanged.connect(self._apply_filters)

        root.addSpacing(12)  # separador visual

        # ───────────── Área centr al (scroll) ─────────────
        self._scroll = QScrollArea(widgetResizable=True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._inner = QWidget()
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll.setWidget(self._inner)
        root.addWidget(self._scroll, 1)

        # ───────────── Barra inferior de acciones ────────
        btn_bar = QHBoxLayout()
        self.btn_view_favs = QPushButton("Ver Favoritos")
        self.btn_fav = QPushButton("☆ Favorito")
        self.btn_next = QPushButton("Siguiente")

        self.btn_view_favs.clicked.connect(self._toggle_favs_view)
        self.btn_fav.clicked.connect(
            lambda: self._toggle_fav(self._current_tip["id"],
                                     bool(self._current_tip["favorito"]))
            if self._current_tip else None
        )
        self.btn_next.clicked.connect(
            lambda: self._mark_learned_and_refresh(self._current_tip["id"])
            if self._current_tip else None
        )

        btn_bar.addWidget(self.btn_view_favs)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_fav)
        btn_bar.addWidget(self.btn_next)
        root.addLayout(btn_bar)

        # ───────────── Atajos de teclado ─────────────
        QShortcut(QKeySequence("F"), self, activated=self._shortcut_toggle_fav)
        QShortcut(QKeySequence("Right"), self, activated=self._shortcut_next)
        QShortcut(QKeySequence("Escape"), self, activated=self._shortcut_back)

        # Carga inicial
        self._show_tip()

    # ╔════════════════════════ DB HELPERS ═════════════════════╗
    def _populate_filter_values(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            cat = sorted({r[0] for r in conn.execute(
                "SELECT DISTINCT categoria FROM Consejos WHERE categoria NOT NULL")})
            lvl = sorted({r[0] for r in conn.execute(
                "SELECT DISTINCT nivel FROM Consejos WHERE nivel NOT NULL")})
        for c in cat:
            self.cmb_cat.addItem(c)
        for l in lvl:
            self.cmb_level.addItem(l)

    def _fetch_random_tip(self) -> Optional[sqlite3.Row]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, texto, codigo_ejemplo, favorito, categoria, nivel "
                "FROM Consejos WHERE estado='Pendiente' ORDER BY RANDOM() LIMIT 1"
            )
            tip = cur.fetchone()
            if tip:
                return tip
            cur.execute(
                "SELECT id, texto, codigo_ejemplo, favorito, categoria, nivel "
                "FROM Consejos ORDER BY RANDOM() LIMIT 1"
            )
            return cur.fetchone()

    def _fetch_filtered(self) -> List[sqlite3.Row]:
        cat = self.cmb_cat.currentText()
        lvl = self.cmb_level.currentText()
        txt = self.txt_search.text().strip().lower()

        clauses, params = [], []
        if cat != "Todas":
            clauses.append("categoria=?")
            params.append(cat)
        if lvl != "Todos":
            clauses.append("nivel=?")
            params.append(lvl)
        if txt:
            clauses.append("(lower(texto) LIKE ? OR lower(codigo_ejemplo) LIKE ?)")
            params += [f"%{txt}%"] * 2

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = ("SELECT id, texto, codigo_ejemplo, favorito, categoria, nivel "
               f"FROM Consejos {where} ORDER BY RANDOM()")
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            return list(conn.execute(sql, params))

    def _fetch_favorites(self) -> List[sqlite3.Row]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT id, texto, codigo_ejemplo, favorito, categoria, nivel, fecha_aprendido "
                "FROM Consejos WHERE favorito=1 "
                "ORDER BY (fecha_aprendido IS NULL), datetime(fecha_aprendido) DESC"
            ).fetchall()

    # ╔════════════════════════ UI BUILDERS ════════════════════╗
    def _make_card(self, tip: sqlite3.Row) -> QGroupBox:
        card = QGroupBox()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        lay = QVBoxLayout(card)
        lay.setSpacing(10)

        txt = QPlainTextEdit(tip["texto"])
        txt.setReadOnly(True)
        txt.setFrameStyle(QFrame.Shape.NoFrame)
        lay.addWidget(txt, 1)

        code = QPlainTextEdit(tip["codigo_ejemplo"] or "")
        code.setReadOnly(True)
        code.setFrameStyle(QFrame.Shape.NoFrame)
        lay.addWidget(code, 1)

        meta = QLabel(
            f"<i>Categoría:</i> {tip['categoria'] or '—'} &nbsp;·&nbsp; "
            f"<i>Nivel:</i> {tip['nivel'] or '—'}"
        )
        meta.setAlignment(Qt.AlignmentFlag.AlignRight)
        meta.setStyleSheet("color:#fff;font-size:11px;")
        lay.addWidget(meta)

        return card

    # ╔════════════════════════ VIEWS ═════════════════════════╗
    def _reset_filters(self) -> None:
        self.cmb_cat.setCurrentIndex(0)
        self.cmb_level.setCurrentIndex(0)
        self.txt_search.clear()

    def _apply_filters(self) -> None:
        if self._showing_favs:
            return

        rows = self._fetch_filtered()
        clear_layout(self._inner_lay)

        if not rows:
            self._inner_lay.addWidget(QLabel("Sin resultados para ese filtro."))
            self._current_tip = None
        else:
            # sin filtros => muestra solo uno
            if (self.cmb_cat.currentText() == "Todas"
                    and self.cmb_level.currentText() == "Todos"
                    and not self.txt_search.text().strip()):
                rows = [rows[0]]

            for r in rows:
                self._inner_lay.addWidget(self._make_card(r))
            self._current_tip = rows[0]

        self._showing_favs = False
        self._update_fav_button()
        self._scroll.verticalScrollBar().setValue(0)

    def _show_tip(self) -> None:
        clear_layout(self._inner_lay)
        tip = self._fetch_random_tip()
        self._current_tip = tip

        if tip is None:
            self._inner_lay.addWidget(QLabel("No hay consejos en la base de datos."))
        else:
            self._inner_lay.addWidget(self._make_card(tip))

        self._showing_favs = False
        self._update_fav_button()
        self._scroll.verticalScrollBar().setValue(0)

    def _show_favorites(self) -> None:
        clear_layout(self._inner_lay)
        favs = self._fetch_favorites()
        if not favs:
            self._inner_lay.addWidget(QLabel("Todavía no has marcado favoritos."))
            self._current_tip = None
        else:
            for tip in favs:
                self._inner_lay.addWidget(self._make_card(tip))
            self._current_tip = favs[0]

        self._showing_favs = True
        self._update_fav_button()
        self._scroll.verticalScrollBar().setValue(0)

    def _toggle_favs_view(self) -> None:
        if self._showing_favs:
            self._showing_favs = False
            self._apply_filters()
        else:
            self._show_favorites()

        self.btn_view_favs.setText(
            "Ver favoritos" if not self._showing_favs else "← Volver"
        )

    # ╔════════════════════════ ACTIONS ═══════════════════════╗
    def _update_fav_button(self) -> None:
        if self._current_tip:
            self.btn_fav.setEnabled(True)
            self.btn_fav.setText("⭐ Favorito" if self._current_tip["favorito"] else "☆ Favorito")
        else:
            self.btn_fav.setEnabled(False)
            self.btn_fav.setText("☆ Favorito")

    def _toggle_fav(self, tip_id: int, is_fav: bool) -> None:
        nuevo = 0 if is_fav else 1
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("UPDATE Consejos SET favorito=? WHERE id=?", (nuevo, tip_id))
            conn.commit()

        QMessageBox.information(
            self, "Consejos",
            "Quitado Favorito" if is_fav else "Marcado Favorito"
        )

        if self._showing_favs:
            self._show_favorites()
        else:
            self._apply_filters()

    def _mark_learned_and_refresh(self, tip_id: int) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE Consejos SET estado='Aprendido', fecha_aprendido=? WHERE id=?",
                (datetime.now().isoformat(timespec='seconds'), tip_id),
            )
            conn.commit()
        self._apply_filters()

    # ╔════════════════════════ SHORTCUTS ═════════════════════╗
    def _shortcut_toggle_fav(self) -> None:
        if not self._showing_favs and self._current_tip:
            self._toggle_fav(self._current_tip["id"], bool(self._current_tip["favorito"]))

    def _shortcut_next(self) -> None:
        if not self._showing_favs and self._current_tip:
            self._mark_learned_and_refresh(self._current_tip["id"])

    def _shortcut_back(self) -> None:
        if self._showing_favs:
            self._toggle_favs_view()