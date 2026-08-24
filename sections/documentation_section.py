#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sections/documentation_section.py  -  Documentation
Refactored 28-Apr-2025
"""

from __future__ import annotations
import os
import re
import shutil
import sqlite3
import webbrowser
import time
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QScrollArea, QDialog, QFormLayout, QDialogButtonBox,
    QPlainTextEdit, QMessageBox, QGridLayout, QFileDialog, QTextEdit
)

from utils import (
    BASE_DIR, DATA_DIR,
    fetchall, fetchone, exec_sql,
    clear_layout, get_relative_path_or_copy, RepoCard
)

# ──────────────────────────────────────────────────────────────────────────────
# Documents root directory
DOCS_DIR = DATA_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Category settings and icon helpers
ICONS_DIR = BASE_DIR / "icons"
ICONS_DIR.mkdir(exist_ok=True)

_MAX_ICON   = 2 * 1024 * 1024  # 2 MB
_VALID_EXTS = {".png", ".jpg", ".jpeg", ".ico"}
_SLUG_RX    = re.compile(r"[^A-Za-z0-9._-]+")
_PIX_CACHE: dict[str, QPixmap] = {}  # cache: absolute path -> QPixmap

def _slugify(txt: str) -> str:
    return (_SLUG_RX.sub("_", txt.strip()) or "unnamed")[:50]

def _copy_icon(src: str, categoria: str) -> str:
    """
    Copies an external icon into icons/<categoria>/ and returns the
    project-relative path. If it is already inside BASE_DIR,
    it returns the relative path directly.
    """
    if not src:
        return ""
    src_p = Path(src).resolve()
    try:
        # Already inside the project
        return src_p.relative_to(BASE_DIR).as_posix()
    except ValueError:
        pass
    # validate extension and size
    if src_p.suffix.lower() not in _VALID_EXTS:
        raise ValueError("Formato no admitido (png/jpg/jpeg/ico).")
    if src_p.stat().st_size > _MAX_ICON:
        raise ValueError("Icono demasiado grande (>2 MB).")
    # copy into icons/<categoria>/ folder
    subdir = ICONS_DIR / _slugify(categoria)
    subdir.mkdir(parents=True, exist_ok=True)
    dest = subdir / f"{_slugify(categoria)}_{src_p.name}"
    if not dest.exists():
        shutil.copy2(src_p, dest)
    return dest.relative_to(BASE_DIR).as_posix()

def _pixmap(rel: str) -> Optional[QPixmap]:
    """
    Carga un QPixmap escalado a 80×80 desde la ruta relativa
    (resolviendo BASE_DIR) y lo cachea.
    """
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

# ──────────────────────────────────────────────────────────────────────────────
# Category settings table
exec_sql("""
CREATE TABLE IF NOT EXISTS CategorySettings (
    categoria              TEXT PRIMARY KEY,
    carpeta_predeterminada TEXT NOT NULL,
    icono                  TEXT
);
""")

# ──────────────────────────────────────────────────────────────────────────────
class CategorySettingsDialog(QDialog):
    """Dialog to create/edit a category."""
    def __init__(
        self,
        parent,
        categoria: str = "",
        carpeta: str = "",
        icono: str = ""
    ):
        super().__init__(parent)
        self.setWindowTitle("Ajustes de Categoría")
        self.resize(520, 240)
        form = QFormLayout(self)

        # Category name
        self.txt_name = QLineEdit(categoria)
        form.addRow("Nombre categoría *:", self.txt_name)

        # Default folder
        self.txt_folder = QLineEdit(carpeta)
        btn_folder = QPushButton("…")
        btn_folder.clicked.connect(self._browse_folder)
        row_f = QHBoxLayout()
        row_f.addWidget(self.txt_folder, 1)
        row_f.addWidget(btn_folder)
        w_folder = QWidget()
        w_folder.setLayout(row_f)
        form.addRow("Carpeta destino *:", w_folder)

        # Icon
        self.txt_icon = QLineEdit(icono)
        btn_icon = QPushButton("…")
        btn_icon.clicked.connect(self._browse_icon)
        row_i = QHBoxLayout()
        row_i.addWidget(self.txt_icon, 1)
        row_i.addWidget(btn_icon)
        w_icon = QWidget()
        w_icon.setLayout(row_i)
        form.addRow("Icono:", w_icon)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addWidget(bb)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta", str(DOCS_DIR)
        )
        if path:
            self.txt_folder.setText(path)

    def _browse_icon(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar icono", str(BASE_DIR),
            "Imágenes (*.png *.jpg *.jpeg *.ico)"
        )
        if path:
            self.txt_icon.setText(path)

    def data(self) -> dict[str, str]:
        return {
            "nombre":  self.txt_name.text().strip(),
            "carpeta": self.txt_folder.text().strip(),
            "icono":   self.txt_icon.text().strip(),
        }

# ──────────────────────────────────────────────────────────────────────────────
class DocEntryDialog(QDialog):
    """Dialog to create/edit an entry."""
    def __init__(
        self,
        parent,
        *,
        data: Optional[dict[str, Any]] = None,
        categoria: str = ""
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Entrada de Documentación")
        self.resize(520, 360)
        form = QFormLayout(self)
        d = data or {}

        self.txt_titulo = QLineEdit(d.get("titulo", ""))
        self.cmb_tipo   = QComboBox()
        self.cmb_tipo.addItems(["Local", "Externo"])
        if d.get("tipo"):
            self.cmb_tipo.setCurrentText(d["tipo"])

        self.txt_ruta = QLineEdit(d.get("ruta", ""))
        btn_browse = QPushButton("…")
        btn_browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.txt_ruta, 1)
        row.addWidget(btn_browse)
        w_ruta = QWidget()
        w_ruta.setLayout(row)

        self.txt_desc = QPlainTextEdit(d.get("descripcion", ""))
        self.txt_desc.setMaximumHeight(90)

        form.addRow("Título *:",     self.txt_titulo)
        form.addRow("Tipo *:",       self.cmb_tipo)
        form.addRow("Ruta / URL *:", w_ruta)
        form.addRow("Descripción:",  self.txt_desc)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addWidget(bb)

        self._categoria = categoria

    def _browse(self):
        if self.cmb_tipo.currentText() == "Local":
            path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo")
            if path:
                self.txt_ruta.setText(path)

    def data(self) -> dict[str, str]:
        return {
            "categoria":   self._categoria,
            "titulo":      self.txt_titulo.text().strip(),
            "tipo":        self.cmb_tipo.currentText(),
            "ruta":        self.txt_ruta.text().strip(),
            "descripcion": self.txt_desc.toPlainText().strip(),
        }

# ──────────────────────────────────────────────────────────────────────────────
class FileCreatorDialog(QDialog):
    """Editor WYSIWYG para crear archivos HTML."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Crear nuevo documento")
        self.resize(600, 550)
        v = QVBoxLayout(self)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Título")
        v.addWidget(self.txt_title)

        self.txt_desc = QPlainTextEdit()
        self.txt_desc.setPlaceholderText("Descripción")
        self.txt_desc.setMaximumHeight(80)
        v.addWidget(self.txt_desc)

        self.editor = QTextEdit()
        self.editor.setAcceptRichText(True)
        v.addWidget(self.editor, 1)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def data(self) -> dict[str, str]:
        return {
            "titulo":      self.txt_title.text().strip(),
            "descripcion": self.txt_desc.toPlainText().strip(),
            "contenido":   self.editor.toHtml().strip(),
        }

    def save_to_file(self, carpeta: str, titulo: str) -> Optional[tuple[str, str]]:
        d = self.data()
        if not d["titulo"] or not d["contenido"]:
            return None
        slug = "".join(c if c.isalnum() else "_" for c in titulo)[:50] or "untitled"
        fname = f"{slug}_{int(time.time())}.html"
        dest = Path(carpeta)
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / fname
        with open(path, "w", encoding="utf-8") as f:
            f.write(d["contenido"])
        return str(path), d["descripcion"]

# ──────────────────────────────────────────────────────────────────────────────
class DocumentationSection(QWidget):
    """Full Documentation section."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._build_index()

    def _build_index(self):
        """Categories screen."""
        clear_layout(self._layout)
        bar = QHBoxLayout()
        self.txt_bus_cat = QLineEdit(placeholderText="Buscar categoría…")
        bar.addWidget(QLabel("Buscar:"))
        bar.addWidget(self.txt_bus_cat)
        bar.addStretch()
        self._layout.addLayout(bar)

        scroll = QScrollArea(widgetResizable=True)
        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setSpacing(16)
        scroll.setWidget(container)
        self._layout.addWidget(scroll, 1)

        self.txt_bus_cat.textChanged.connect(self._refresh_categories)
        self._refresh_categories()

    def _refresh_categories(self):
        """Rebuild the category grid with icons on the cards."""
        clear_layout(self.grid)
        filtro = self.txt_bus_cat.text().strip().lower()

        settings = [r["categoria"] for r in fetchall("SELECT categoria FROM CategorySettings")]
        dirs = [p.name for p in DOCS_DIR.iterdir() if p.is_dir()]
        cats = sorted(set(settings + dirs))
        cats = [c for c in cats if filtro in c.lower()]

        COLS = 4
        for idx, cat in enumerate(cats):
            r, c = divmod(idx, COLS)
            # get icon from DB
            row = fetchone(
                "SELECT icono FROM CategorySettings WHERE categoria=?",
                (cat,)
            ) or {}
            icon_rel = row.get("icono", "")
            pm = _pixmap(icon_rel)

            btn = QPushButton(cat)
            btn.setFixedSize(165, 165)
            if pm:
                btn.setIcon(QIcon(pm))
                btn.setIconSize(QSize(48, 48))
            btn.setStyleSheet(
                "font-weight: bold; "
                "font-size: 16px; "
                "text-align: center;"
            )
            btn.clicked.connect(lambda _, cc=cat: self._open_category(cc))
            self.grid.addWidget(btn, r, c)

        # new-category tile
        idx = len(cats)
        r, c = divmod(idx, COLS)
        plus = QPushButton("+")
        plus.setFixedSize(160,160)
        plus.setStyleSheet("border:2px dashed #666;font-size:24px;")
        plus.clicked.connect(self._create_category)
        self.grid.addWidget(plus, r, c)

    def _create_category(self):
        """Opens the dialog to create a new category."""
        dlg = CategorySettingsDialog(self, "", str(DOCS_DIR), "")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["nombre"] or not d["carpeta"]:
            QMessageBox.warning(self, "Campos", "Nombre y carpeta obligatorios.")
            return
        try:
            ic_rel = _copy_icon(d["icono"], d["nombre"])
        except ValueError as e:
            QMessageBox.warning(self, "Icono", str(e))
            return
        Path(d["carpeta"]).mkdir(parents=True, exist_ok=True)
        exec_sql("""
            INSERT INTO CategorySettings(categoria,carpeta_predeterminada,icono)
            VALUES(?,?,?)
            ON CONFLICT(categoria) DO UPDATE SET
              carpeta_predeterminada=excluded.carpeta_predeterminada,
              icono=excluded.icono
        """, (d["nombre"], d["carpeta"], ic_rel))
        self._build_index()

    def _open_category(self, categoria: str):
        """Detail of one category."""
        clear_layout(self._layout)
        self._categoria = categoria

        row = fetchone(
            "SELECT carpeta_predeterminada,icono FROM CategorySettings WHERE categoria=?",
            (categoria,)
        )
        carpeta_def = row["carpeta_predeterminada"] if row else str(DOCS_DIR/categoria)
        icono_rel   = row["icono"]                if row else ""

        # top row
        top = QHBoxLayout()
        btn_back = QPushButton("◀️ Volver")
        btn_back.clicked.connect(self._build_index)
        btn_open = QPushButton("📂 Abrir carpeta")
        btn_open.clicked.connect(lambda: os.startfile(carpeta_def)
                                 if os.name=="nt"
                                 else webbrowser.open(carpeta_def))
        btn_edit = QPushButton("✏️ Editar categoría")
        btn_edit.clicked.connect(lambda: self._edit_category(categoria, carpeta_def, icono_rel))
        btn_del  = QPushButton("🗑️ Eliminar categoría")
        btn_del.clicked.connect(lambda: self._delete_category(categoria))
        top.addWidget(btn_back)
        top.addStretch()
        top.addWidget(btn_open)
        top.addWidget(btn_edit)
        top.addWidget(btn_del)
        self._layout.addLayout(top)

        # title + icon
        lbl = QLabel(f"📚 {categoria or 'Nueva categoría'}")
        lbl.setStyleSheet("font-size:20px;font-weight:bold;")
        self._layout.addWidget(lbl)
        if icono_rel:
            pm = _pixmap(icono_rel)
            if pm:
                ico = QLabel()
                ico.setPixmap(pm)
                ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._layout.addWidget(ico)

        # entry filters
        bar = QHBoxLayout()
        self.txt_bus = QLineEdit(placeholderText="Buscar entrada…")
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItems(["Todos","Local","Externo"])
        bar.addWidget(QLabel("Buscar:")); bar.addWidget(self.txt_bus)
        bar.addWidget(QLabel("Tipo:"));   bar.addWidget(self.cmb_tipo)
        bar.addStretch()
        self._layout.addLayout(bar)

        # entries container
        scroll = QScrollArea(widgetResizable=True)
        container = QWidget()
        self.v_entries = QVBoxLayout(container)
        self.v_entries.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        self._layout.addWidget(scroll, 1)

        # actions
        row = QHBoxLayout()
        btn_new    = QPushButton("➕ Nueva entrada")
        btn_new.clicked.connect(self._new_entry)
        btn_create = QPushButton("📄 Crear Archivo")
        btn_create.clicked.connect(self._create_file)
        row.addWidget(btn_new)
        row.addWidget(btn_create)
        self._layout.addLayout(row)

        # signals
        self.txt_bus.textChanged.connect(self._refresh_entries)
        self.cmb_tipo.currentIndexChanged.connect(self._refresh_entries)
        self._refresh_entries()

    def _edit_category(self, categoria, carpeta, icono_rel):
        dlg = CategorySettingsDialog(self, categoria, carpeta, icono_rel)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if categoria and d["nombre"] != categoria:
            exec_sql("UPDATE Documentacion SET categoria=? WHERE categoria=?", (d["nombre"], categoria))
            exec_sql("UPDATE CategorySettings SET categoria=? WHERE categoria=?", (d["nombre"], categoria))
            (DOCS_DIR/categoria).rename(DOCS_DIR/d["nombre"])
        try:
            ic_rel = _copy_icon(d["icono"], d["nombre"])
        except ValueError as e:
            QMessageBox.warning(self, "Icono", str(e))
            return
        exec_sql("""
            INSERT INTO CategorySettings(categoria,carpeta_predeterminada,icono)
            VALUES(?,?,?)
            ON CONFLICT(categoria) DO UPDATE SET
              carpeta_predeterminada=excluded.carpeta_predeterminada,
              icono=excluded.icono
        """, (d["nombre"], d["carpeta"], ic_rel))
        _PIX_CACHE.clear()
        self._open_category(d["nombre"])

    def _delete_category(self, categoria):
        if not categoria:
            return
        if QMessageBox.question(self, "Eliminar categoría",
                                f"¿Eliminar categoría «{categoria}» y todas sus entradas?") \
           != QMessageBox.StandardButton.Yes:
            return
        exec_sql("DELETE FROM Documentacion WHERE categoria=?", (categoria,))
        exec_sql("DELETE FROM CategorySettings WHERE categoria=?", (categoria,))
        folder = DOCS_DIR / categoria
        if folder.exists():
            for item in folder.iterdir():
                item.unlink()
            folder.rmdir()
        self._build_index()

    def _refresh_entries(self):
        clear_layout(self.v_entries)
        texto = self.txt_bus.text().strip().lower()
        tipo  = self.cmb_tipo.currentText()
        conds, params = [], []
        if self._categoria:
            conds.append("categoria=?"); params.append(self._categoria)
        if texto:
            conds.append("lower(titulo) LIKE ?"); params.append(f"%{texto}%")
        if tipo != "Todos":
            conds.append("tipo=?"); params.append(tipo)
        q = "SELECT * FROM Documentacion"
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY titulo"
        for doc in fetchall(q, params):
            card = RepoCard(doc["titulo"])
            lbl = QLabel(doc.get("descripcion", "(sin descripción)"))
            lbl.setWordWrap(True)
            card.add_left(lbl)
            actions = QWidget()
            al = QVBoxLayout(actions)
            b_open = QPushButton("Abrir")
            b_open.clicked.connect(lambda _, d=doc: self._open(d))
            b_edit = QPushButton("Editar")
            b_edit.clicked.connect(lambda _, d=doc: self._edit_entry(d))
            b_del  = QPushButton("Eliminar")
            b_del.clicked.connect(lambda _, i=doc["id"]: self._delete(i))
            for b in (b_open, b_edit, b_del):
                al.addWidget(b)
            card.add_right(actions)
            self.v_entries.addWidget(card)

    def _new_entry(self):
        dlg = DocEntryDialog(self, categoria=self._categoria)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["titulo"] or not d["ruta"]:
            QMessageBox.warning(self, "Campos", "Título y ruta/URL obligatorios.")
            return
        row = fetchone(
            "SELECT carpeta_predeterminada FROM CategorySettings WHERE categoria=?",
            (self._categoria,)
        ) or {}
        carpeta = row.get("carpeta_predeterminada") or str(DOCS_DIR/self._categoria)
        if d["tipo"] == "Local":
            ruta = get_relative_path_or_copy(d["ruta"], Path(carpeta), allow_copy=True)
            if not ruta:
                QMessageBox.warning(self, "Error", "No se pudo copiar/relativizar el archivo.")
                return
        else:
            ruta = d["ruta"]
        try:
            exec_sql(
                "INSERT INTO Documentacion(categoria,titulo,tipo,ruta,descripcion) "
                "VALUES(?,?,?,?,?)",
                (self._categoria, d["titulo"], d["tipo"], ruta, d["descripcion"])
            )
            self._refresh_entries()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Duplicado", "Ya existe una entrada con ese título.")

    def _create_file(self):
        row = fetchone(
            "SELECT carpeta_predeterminada FROM CategorySettings WHERE categoria=?",
            (self._categoria,)
        ) or {}
        carpeta = row.get("carpeta_predeterminada") or str(DOCS_DIR/self._categoria)
        dlg = FileCreatorDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        result = dlg.save_to_file(carpeta, dlg.data()["titulo"])
        if not result:
            QMessageBox.warning(self, "Error", "Título y contenido obligatorios.")
            return
        fname, desc = result
        rel = Path(fname).relative_to(BASE_DIR).as_posix()
        exec_sql(
            "INSERT INTO Documentacion(categoria,titulo,tipo,ruta,descripcion) VALUES(?,?,?,?,?)",
            (self._categoria, dlg.data()["titulo"], "Local", rel, desc)
        )
        self._refresh_entries()

    def _edit_entry(self, doc):
        dlg = DocEntryDialog(self, data=doc, categoria=self._categoria)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        row = fetchone(
            "SELECT carpeta_predeterminada FROM CategorySettings WHERE categoria=?",
            (self._categoria,)
        ) or {}
        carpeta = row.get("carpeta_predeterminada") or str(DOCS_DIR/self._categoria)
        if d["tipo"] == "Local":
            ruta = get_relative_path_or_copy(d["ruta"], Path(carpeta), allow_copy=True)
        else:
            ruta = d["ruta"]
        exec_sql(
            "UPDATE Documentacion SET titulo=?,tipo=?,ruta=?,descripcion=? WHERE id=?",
            (d["titulo"], d["tipo"], ruta, d["descripcion"], doc["id"])
        )
        self._refresh_entries()

    def _delete(self, eid):
        if QMessageBox.question(self, "Eliminar", "¿Eliminar esta entrada?") \
           != QMessageBox.StandardButton.Yes:
            return
        exec_sql("DELETE FROM Documentacion WHERE id=?", (eid,))
        self._refresh_entries()

    def _open(self, doc):
        if doc["tipo"] == "Externo":
            webbrowser.open(doc["ruta"])
        else:
            row = fetchone(
                "SELECT carpeta_predeterminada FROM CategorySettings WHERE categoria=?",
                (self._categoria,)
            ) or {}
            carpeta = row.get("carpeta_predeterminada") or str(DOCS_DIR/self._categoria)
            path = Path(carpeta) / doc["ruta"]
            if path.exists():
                webbrowser.open(path.as_uri())
            else:
                QMessageBox.warning(self, "Archivo", "No encontrado.")