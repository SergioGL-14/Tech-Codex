#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sections/diary_section.py · Diario de Desarrollo
Versión refactor 26-abr-2025 (con rutas de carpetas)
"""

from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Optional, Tuple

from PyQt6.QtCore import Qt, QDate, QSize, QUrl
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils import BASE_DIR, clear_layout, exec_sql, fetchall, fetchone, DB_PATH

# ──────────────────────────────────────────────────────────────────────────────
LANGUAGES: Final[list[str]] = ["", "Python", "PowerShell", "JavaScript", "C#", "Go", "Rust", "Otro"]
STATES:    Final[list[str]] = ["En curso", "Pausado", "Finalizado"]

CARD      = 140
ICONS_DIR = BASE_DIR / "icons"; ICONS_DIR.mkdir(exist_ok=True)
_MAX_ICON   = 2 * 1024 * 1024
_VALID_EXTS = {".png", ".jpg", ".jpeg", ".ico"}

_SLUG_RX   = re.compile(r"[^A-Za-z0-9._-]+")
_PIX_CACHE: dict[str, QPixmap] = {}


def _slugify(txt: str) -> str:
    return (_SLUG_RX.sub("_", txt.strip()) or "unnamed")[:50]


def _copy_icon(src: str, project: str) -> str:
    if not src:
        return ""
    src_p = Path(src).resolve()
    try:
        return src_p.relative_to(BASE_DIR).as_posix()
    except ValueError:
        pass
    if src_p.suffix.lower() not in _VALID_EXTS:
        raise ValueError("Formato no admitido (png / jpg / ico).")
    if src_p.stat().st_size > _MAX_ICON:
        raise ValueError("Imagen > 2 MB.")
    dest_dir = ICONS_DIR / _slugify(project)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{_slugify(project)}_{src_p.name}"
    if not dest.exists():
        shutil.copy2(src_p, dest)
    return dest.relative_to(BASE_DIR).as_posix()


def _pixmap(rel: str) -> Optional[QPixmap]:
    if not rel:
        return None
    abs_path = (BASE_DIR / rel).as_posix()
    pm = _PIX_CACHE.get(abs_path)
    if pm is None:
        raw = QPixmap(abs_path)
        if raw.isNull():
            return None
        pm = raw.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
        _PIX_CACHE[abs_path] = pm
    return pm


def _ensure_columns() -> None:
    """Añade columnas nuevas a DiariosDesarrollo si no existen aún."""
    with sqlite3.connect(DB_PATH) as c:
        # Activar foreign keys por si acaso
        c.execute("PRAGMA foreign_keys = ON;")
        cur = c.cursor()
        for col, ddl in (
            ("lenguaje", "TEXT"),
            ("estado",   "TEXT DEFAULT 'En curso'"),
            ("icono",    "TEXT"),
            ("ruta",     "TEXT"),
        ):
            try:
                cur.execute(f"ALTER TABLE DiariosDesarrollo ADD COLUMN {col} {ddl}")
            except sqlite3.OperationalError:
                # La columna ya existe
                pass
        c.commit()

# Ejecutamos la migración al cargar el módulo
_ensure_columns()


class _DlgBase(QDialog):
    def _buttons(self) -> QDialogButtonBox:
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        return bb


class DiarioDialog(_DlgBase):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuevo Diario")
        self.resize(440, 260)
        form = QFormLayout(self)
        self.txt_tit  = QLineEdit()
        self.txt_desc = QTextEdit(); self.txt_desc.setMaximumHeight(90)
        self.cmb_lang = QComboBox();  self.cmb_lang.addItems(LANGUAGES)
        self.cmb_state= QComboBox();  self.cmb_state.addItems(STATES)
        form.addRow("Título *:",      self.txt_tit)
        form.addRow("Descripción:",   self.txt_desc)
        form.addRow("Lenguaje:",      self.cmb_lang)
        form.addRow("Estado:",        self.cmb_state)
        form.addWidget(self._buttons())

    def data(self) -> dict[str, str]:
        return {
            "titulo":      self.txt_tit.text().strip(),
            "descripcion": self.txt_desc.toPlainText().strip(),
            "lenguaje":    self.cmb_lang.currentText(),
            "estado":      self.cmb_state.currentText(),
        }


class DiarioMetaDialog(_DlgBase):
    def __init__(self, parent, *, lenguaje: str, estado: str, icono: str, ruta: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar características")
        self.resize(440, 240)
        form = QFormLayout(self)
        # Lenguaje y estado
        self.cmb_lang = QComboBox(); self.cmb_lang.addItems(LANGUAGES)
        self.cmb_lang.setCurrentText(lenguaje or "")
        self.cmb_state= QComboBox(); self.cmb_state.addItems(STATES)
        self.cmb_state.setCurrentText(estado or STATES[0])
        # Icono
        self.lbl_icon = QLabel(Path(icono).name if icono else "(sin icono)")
        self._icon_path = icono
        btn_browse = QPushButton("…"); btn_browse.clicked.connect(self._browse)
        h1 = QHBoxLayout(); h1.addWidget(self.lbl_icon); h1.addWidget(btn_browse)
        # Carpeta
        self.lbl_ruta = QLabel(Path(ruta).name if ruta else "(sin carpeta)")
        self._ruta_path = ruta
        btn_ruta = QPushButton("…"); btn_ruta.clicked.connect(self._browse_ruta)
        h2 = QHBoxLayout(); h2.addWidget(self.lbl_ruta); h2.addWidget(btn_ruta)

        form.addRow("Lenguaje:", self.cmb_lang)
        form.addRow("Estado:",   self.cmb_state)
        form.addRow("Icono:",    h1)
        form.addRow("Carpeta:",  h2)
        form.addWidget(self._buttons())

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir icono", str(BASE_DIR), "Imágenes (*.png *.jpg *.jpeg *.ico)"
        )
        if path:
            self._icon_path = path
            self.lbl_icon.setText(Path(path).name)

    def _browse_ruta(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta del proyecto", str(BASE_DIR)
        )
        if path:
            self._ruta_path = path
            self.lbl_ruta.setText(Path(path).name)

    def data(self) -> Tuple[str, str, str, str]:
        return (
            self.cmb_lang.currentText(),
            self.cmb_state.currentText(),
            self._icon_path,
            self._ruta_path,
        )


class EntradaDialog(_DlgBase):
    def __init__(self, parent, *, titulo: str = "", contenido: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Entrada")
        self.resize(parent.width() - 80, parent.height() - 140)
        form = QFormLayout(self)
        self.txt_tit = QLineEdit(titulo)
        self.txt_con = QTextEdit(); self.txt_con.setAcceptRichText(True)
        self.txt_con.setHtml(contenido); self.txt_con.setMinimumHeight(240)
        form.addRow("Título *:",    self.txt_tit)
        form.addRow("Contenido *:", self.txt_con)
        form.addWidget(self._buttons())

    def data(self) -> dict[str, str]:
        return {"titulo": self.txt_tit.text().strip(),
                "contenido": self.txt_con.toHtml().strip()}


class DiarySection(QWidget):
    COLS = 5

    def __init__(self, db_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._build_index()

    def _build_index(self) -> None:
        clear_layout(self._layout)
        # ── barra de filtros ──
        bar = QHBoxLayout()
        self.txt_find  = QLineEdit(placeholderText="Buscar…")
        self.cmb_lang  = QComboBox(); self.cmb_lang.addItem("Todos")
        self.cmb_state = QComboBox(); self.cmb_state.addItems(["Todos", *STATES])
        for w, lbl in ((self.txt_find, "Buscar:"), (self.cmb_lang, "Lenguaje:"), (self.cmb_state, "Estado:")):
            bar.addWidget(QLabel(lbl)); bar.addWidget(w)
        bar.addStretch()
        self._layout.addLayout(bar)

        # ── área scroll ──
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(14)
        self.grid.setColumnStretch(self.COLS - 1, 1)

        self.scroll.setWidget(self.container)
        self._layout.addWidget(self.scroll)

        self.txt_find.textChanged.connect(self._reload_grid)
        self.cmb_lang.currentIndexChanged.connect(self._reload_grid)
        self.cmb_state.currentIndexChanged.connect(self._reload_grid)
        self._reload_grid()

    def _reload_grid(self) -> None:
        clear_layout(self.grid)
        rows = fetchall("SELECT * FROM DiariosDesarrollo ORDER BY fecha_creacion DESC")
        if self.cmb_lang.count() == 1:
            for lang in sorted({r["lenguaje"] for r in rows if r["lenguaje"]}):
                self.cmb_lang.addItem(lang)

        f_txt, f_lang, f_state = (
            self.txt_find.text().lower(),
            self.cmb_lang.currentText(),
            self.cmb_state.currentText(),
        )
        visibles = [
            r for r in rows
            if (not f_txt or f_txt in r["titulo"].lower())
            and (f_lang  == "Todos" or r["lenguaje"] == f_lang)
            and (f_state == "Todos" or r["estado"]   == f_state)
        ]

        for i, r in enumerate(visibles):
            rr, cc = divmod(i, self.COLS)
            self.grid.addWidget(self._make_card(r), rr, cc)

        rr, cc = divmod(len(visibles), self.COLS)
        plus = QPushButton("+")
        plus.setFixedSize(CARD, CARD)
        plus.setStyleSheet("border:2px dashed #666;font-size:26px;")
        plus.clicked.connect(self._new_diary)
        self.grid.addWidget(plus, rr, cc)
        self.grid.setRowStretch(rr + 1, 1)

    def _make_card(self, d: dict[str, Any]) -> QGroupBox:
        # Creamos un QGroupBox
        w = QGroupBox()
        w.setObjectName("cardBox")
        w.setFixedSize(CARD, CARD)

        # Layout vertical sin márgenes extra
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)

        # 1) TÍTULO: arriba, en negrita y blanco
        ttl = QLabel(d["titulo"])
        ttl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ttl.setWordWrap(True)
        ttl.setStyleSheet("color: #eee; font-weight: bold; background: transparent;")
        v.addWidget(ttl)

        # pequeño espacio extra tras el título
        v.addSpacing(2)

        # 2) ICONO: centrado y limpio
        pm = _pixmap(d.get("icono", ""))
        if pm:
            img = QLabel()
            img.setPixmap(pm)
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img.setStyleSheet("border: none; background: transparent;")
            v.addWidget(img, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            # si no hay icono, reservamos espacio aproximado
            v.addSpacing(80)

        # 3) Stretch para empujar el estado hacia el fondo
        v.addStretch()

        # 4) ESTADO: texto pegado al borde inferior, verde si Finalizado
        st = QLabel(d["estado"])
        st.setAlignment(Qt.AlignmentFlag.AlignCenter)
        st.setStyleSheet(
            "color: #31c931; font-size: 10px; background: transparent;"
            if d["estado"] == "Finalizado"
            else "color: #999; font-size: 10px; background: transparent;"
        )
        v.addWidget(st)

        # Click sobre la tarjeta abre el diario
        w.mousePressEvent = lambda _, dia=d: self._open_diary(dia)  # type: ignore
        return w

    def _new_diary(self) -> None:
        dlg = DiarioDialog(self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["titulo"]:
            QMessageBox.warning(self, "Error", "El título no puede estar vacío.")
            return
        try:
            exec_sql(
                "INSERT INTO DiariosDesarrollo(titulo,descripcion,fecha_creacion,lenguaje,estado) VALUES(?,?,?,?,?)",
                (d["titulo"], d["descripcion"], datetime.now().isoformat(), d["lenguaje"], d["estado"])
            )
            self._reload_grid()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Duplicado", "Ya existe un diario con ese título.")

    def _open_diary(self, dia: dict[str, Any]) -> None:
        clear_layout(self._layout)
        self._diario = dia
        self._desc   = True

        # ── barra superior ──
        top = QHBoxLayout()
        btn_back = QPushButton("◀ Volver"); btn_back.clicked.connect(self._build_index)
        self.lbl_order = QLabel(); self.lbl_order.setStyleSheet("color: white; font-size: 14px;")
        self.btn_order = QToolButton(); self.btn_order.setAutoRaise(True)
        self.btn_order.setArrowType(Qt.ArrowType.DownArrow)
        self.btn_order.setIconSize(QSize(24,24))
        self.btn_order.setStyleSheet("color: white;")
        self.btn_order.clicked.connect(self._toggle_order)
        btn_edit = QPushButton("Editar"); btn_edit.clicked.connect(lambda: self._edit_meta(dia))
        top.addWidget(btn_back); top.addStretch()
        top.addWidget(self.lbl_order); top.addWidget(self.btn_order); top.addWidget(btn_edit)
        self._layout.addLayout(top)
        self._update_order_icon()

        # ── cabecera ──
        h = QLabel(f"📘 {dia['titulo']}"); h.setStyleSheet("font-size:22px;font-weight:bold;")
        self._layout.addWidget(h)
        if dia.get("descripcion"):
            dsc = QLabel(dia["descripcion"]); dsc.setWordWrap(True); self._layout.addWidget(dsc)
        meta = QLabel(f"<i>Lenguaje:</i> {dia.get('lenguaje') or '—'}  •  <i>Estado:</i> {dia.get('estado') or '—'}")
        meta.setStyleSheet("color:#999;font-size:11px;")
        self._layout.addWidget(meta)

        # ── filtros entradas ──
        fbar = QHBoxLayout()
        # Botón Abrir Carpeta
        if dia.get("ruta"):
            btn_open = QPushButton("📂 Abrir carpeta")
            btn_open.clicked.connect(lambda _, p=dia["ruta"]: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
            fbar.addWidget(btn_open)

        self.txt_f = QLineEdit(placeholderText="Buscar texto…")
        self.dt_f  = QDateEdit(calendarPopup=True); self.dt_f.setDisplayFormat("dd/MM/yyyy")
        self.dt_f.setDate(QDate(1970,1,1))
        self.dt_t  = QDateEdit(calendarPopup=True); self.dt_t.setDisplayFormat("dd/MM/yyyy")
        self.dt_t.setDate(QDate.currentDate())
        for w,l in ((self.txt_f,"Filtro:"),(self.dt_f,"Desde:"),(self.dt_t,"Hasta:")):
            fbar.addWidget(QLabel(l)); fbar.addWidget(w)
        fbar.addStretch()
        btn_new = QPushButton("➕ Nueva entrada"); btn_new.clicked.connect(lambda: self._new_entry(dia["id"]))
        fbar.addWidget(btn_new)
        self._layout.addLayout(fbar)

        # ── contenedor entradas ──
        self.entries_box = QVBoxLayout()
        self._layout.addLayout(self.entries_box); self._layout.addStretch()
        self._draw_entries()

    def _toggle_order(self) -> None:
        self._desc = not getattr(self, "_desc", True)
        self._update_order_icon()
        self._draw_entries()

    def _update_order_icon(self) -> None:
        if getattr(self, "_desc", True):
            self.btn_order.setArrowType(Qt.ArrowType.DownArrow)
            self.btn_order.setToolTip("Orden descendente (más nuevo primero)")
            self.lbl_order.setText("Orden Descendente")
        else:
            self.btn_order.setArrowType(Qt.ArrowType.UpArrow)
            self.btn_order.setToolTip("Orden ascendente (más viejo primero)")
            self.lbl_order.setText("Orden Ascendente")

    def _draw_entries(self) -> None:
        clear_layout(self.entries_box)
        search = self.txt_f.text().lower()
        f_from = self.dt_f.date().toPyDate()
        f_to   = self.dt_t.date().toPyDate()
        order  = "DESC" if getattr(self, "_desc", True) else "ASC"
        rows = fetchall(
            f"SELECT id,titulo,fecha,contenido FROM EntradasDesarrollo WHERE id_diario=? ORDER BY fecha {order}",
            (self._diario["id"],),
        )
        for ent in rows:
            day = datetime.fromisoformat(ent["fecha"]).date()
            if not (f_from <= day <= f_to):
                continue
            if search and search not in ent["titulo"].lower() and search not in ent["contenido"].lower():
                continue
            gb = QGroupBox(f"{ent['titulo']} — {day.strftime('%d/%m/%Y')}")
            vb = QVBoxLayout(gb)
            brw = QTextBrowser(); brw.setHtml(ent["contenido"]); brw.setMinimumHeight(160)
            vb.addWidget(brw)
            row = QHBoxLayout()
            b_ed = QPushButton("🔧 Editar");  b_ed.clicked.connect(lambda _, i=ent["id"]: self._edit_entry(i))
            b_rm = QPushButton("🗑 Eliminar"); b_rm.clicked.connect(lambda _, i=ent["id"]: self._del_entry(i))
            row.addWidget(b_ed); row.addWidget(b_rm); row.addStretch()
            vb.addLayout(row)
            self.entries_box.addWidget(gb)

    def _edit_meta(self, d: dict[str, Any]) -> None:
        dlg = DiarioMetaDialog(
            self,
            lenguaje=d.get("lenguaje") or "",
            estado=d.get("estado")   or STATES[0],
            icono=d.get("icono")     or "",
            ruta=d.get("ruta")       or "",
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        lang, state, src_icon, ruta = dlg.data()
        try:
            rel = _copy_icon(src_icon, d["titulo"]) if src_icon and not src_icon.startswith(str(BASE_DIR)) else src_icon
        except ValueError as err:
            QMessageBox.warning(self, "Icono", str(err)); return
        exec_sql(
            "UPDATE DiariosDesarrollo SET lenguaje=?, estado=?, icono=?, ruta=? WHERE id=?",
            (lang, state, rel, ruta, d["id"])
        )
        _PIX_CACHE.clear()
        self._open_diary(fetchone("SELECT * FROM DiariosDesarrollo WHERE id=?", (d["id"],)))

    def _new_entry(self, did: int) -> None:
        dlg = EntradaDialog(self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["titulo"] or not d["contenido"]:
            QMessageBox.warning(self, "Error", "Título y contenido obligatorios."); return
        exec_sql("INSERT INTO EntradasDesarrollo(id_diario,titulo,fecha,contenido) VALUES(?,?,?,?)",
                 (did, d["titulo"], datetime.now().isoformat(), d["contenido"]))
        self._draw_entries()

    def _edit_entry(self, eid: int) -> None:
        ent = fetchone("SELECT titulo,contenido FROM EntradasDesarrollo WHERE id=?", (eid,))
        if not ent:
            return
        dlg = EntradaDialog(self, titulo=ent["titulo"], contenido=ent["contenido"])
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["titulo"] or not d["contenido"]:
            QMessageBox.warning(self, "Error", "Título y contenido obligatorios."); return
        exec_sql("UPDATE EntradasDesarrollo SET titulo=?,contenido=? WHERE id=?", (d["titulo"], d["contenido"], eid))
        self._draw_entries()

    def _del_entry(self, eid: int) -> None:
        if QMessageBox.question(self, "Eliminar", "¿Eliminar esta entrada?") != QMessageBox.StandardButton.Yes:
            return
        exec_sql("DELETE FROM EntradasDesarrollo WHERE id=?", (eid,))
        self._draw_entries()