#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sections/scripts_section.py  ·  Repositorio de Scripts
Versión refactorizada 25-abr-2025
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from functools import partial
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QMessageBox, QPlainTextEdit, QDialog, QFormLayout,
    QDialogButtonBox, QSpacerItem
)

from utils import (
    SCRIPTS_DIR, SCRIPT_EXT,
    get_conn, fetchall, exec_sql, clear_layout,
    get_relative_path_or_copy, RepoCard, AssetDialog
)

# ──────────────────────────────── Dialog for adding/editing ────────────────────────────────
class ScriptDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        nombre: str = "",
        descripcion: str = "",
        ruta: str = ""
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Script")
        self.resize(500, 280)
        form = QFormLayout(self)

        self.txt_nombre = QLineEdit(nombre)
        self.txt_desc   = QPlainTextEdit(descripcion); self.txt_desc.setMaximumHeight(100)
        self.txt_ruta   = QLineEdit(ruta)
        btn_browse      = QPushButton("…")
        btn_browse.clicked.connect(self._browse)
        h = QHBoxLayout(); h.addWidget(self.txt_ruta, 1); h.addWidget(btn_browse)
        ruta_widget = QWidget(); ruta_widget.setLayout(h)

        form.addRow("Nombre *:", self.txt_nombre)
        form.addRow("Descripción:", self.txt_desc)
        form.addRow("Ruta (*exe, .ps1, .py, .bat*):", ruta_widget)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addWidget(bb)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar script", str(SCRIPTS_DIR))
        if path:
            self.txt_ruta.setText(path)

    def data(self) -> Tuple[str, str, str]:
        return (
            self.txt_nombre.text().strip(),
            self.txt_desc.toPlainText().strip(),
            self.txt_ruta.text().strip()
        )


# ──────────────────────────────── Main Widget ────────────────────────────────
class ScriptsSection(QWidget):
    """Gestor de scripts sueltos o carpetas de proyecto."""
    def __init__(self, db_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db_path = db_path
        self._build_ui()
        self._refresh_cards("")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # — Barra de búsqueda y acciones —
        bar = QHBoxLayout()
        self.txt_search = QLineEdit(placeholderText="Buscar…")
        btn_add    = QPushButton("➕ Añadir")
        btn_reload = QPushButton("🔄 Recargar")
        bar.addWidget(QLabel("Buscar:")); bar.addWidget(self.txt_search)
        bar.addStretch()
        bar.addWidget(btn_add);    bar.addWidget(btn_reload)
        root.addLayout(bar)

        # — Área scroll con tarjetas —
        scroll = QScrollArea(widgetResizable=True)
        container = QWidget()
        self.lay_cards = QVBoxLayout(container)
        self.lay_cards.setContentsMargins(0,0,0,0)
        self.lay_cards.setSpacing(10)
        self.lay_cards.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

        # señales
        self.txt_search.textChanged.connect(self._on_search)
        btn_add.clicked.connect(self._on_add)
        btn_reload.clicked.connect(self._on_reload)

    def _on_search(self, txt: str) -> None:
        self._refresh_cards(txt)

    def _on_add(self) -> None:
        dlg = ScriptDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        nombre, desc, ruta = dlg.data()
        if not nombre or not ruta:
            QMessageBox.warning(self, "Error", "Nombre y ruta son obligatorios.")
            return

        src = Path(ruta)
        if not src.exists():
            QMessageBox.warning(self, "Error", "Ruta no existe.")
            return

        rel = get_relative_path_or_copy(ruta, SCRIPTS_DIR, allow_copy=True)
        if rel is None:
            QMessageBox.warning(self, "Error", "No se pudo copiar o relativizar.")
            return

        lang = SCRIPT_EXT.get(src.suffix.lower(), "Otro") if src.is_file() else "Otro"
        try:
            exec_sql(
                "INSERT INTO Scripts(nombre,descripcion,lenguaje,ruta_archivo) VALUES(?,?,?,?)",
                (nombre, desc, lang, rel)
            )
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Duplicado", "Ya existe un script con ese nombre.")
            return

        self._refresh_cards(self.txt_search.text())

    def _on_reload(self) -> None:
        SCRIPTS_DIR.mkdir(exist_ok=True)
        added = 0
        with get_conn() as conn:
            cur = conn.cursor()
            for item in SCRIPTS_DIR.iterdir():
                if item.is_dir():
                    # busca <dir>/<dir>.<ext>
                    for ext, lang in SCRIPT_EXT.items():
                        main = item / f"{item.name}{ext}"
                        if main.exists():
                            rel = main.relative_to(SCRIPTS_DIR).as_posix()
                            try:
                                cur.execute(
                                    "INSERT INTO Scripts(nombre,descripcion,lenguaje,ruta_archivo) "
                                    "VALUES(?, 'Sin descripción', ?, ?)",
                                    (item.name, lang, rel)
                                )
                                added += 1
                            except sqlite3.IntegrityError:
                                pass
                            break
                elif item.suffix.lower() in SCRIPT_EXT:
                    rel = item.relative_to(SCRIPTS_DIR).as_posix()
                    try:
                        cur.execute(
                            "INSERT INTO Scripts(nombre,descripcion,lenguaje,ruta_archivo) "
                            "VALUES(?, 'Sin descripción', ?, ?)",
                            (item.stem, SCRIPT_EXT[item.suffix.lower()], rel)
                        )
                        added += 1
                    except sqlite3.IntegrityError:
                        pass
            conn.commit()
        QMessageBox.information(self, "Recarga", f"Añadidos {added} scripts.")
        self._refresh_cards(self.txt_search.text())

    def _refresh_cards(self, filtro: str) -> None:
        # conserva stretch
        stretch = self.lay_cards.takeAt(self.lay_cards.count()-1)
        clear_layout(self.lay_cards)
        self.lay_cards.addItem(stretch)

        rows = fetchall("SELECT * FROM Scripts ORDER BY nombre")
        filtro = filtro.lower()

        for r in rows:
            if filtro and filtro not in r["nombre"].lower():
                continue

            card = RepoCard(r["nombre"])

            # izquierda: descripción / editor
            left = QWidget(); ll = QVBoxLayout(left)
            desc = r["descripcion"] or ""
            if not desc.strip() or desc.startswith("Sin descripción"):
                txt = QPlainTextEdit(desc)
                btn = QPushButton("💾 Guardar")
                btn.clicked.connect(partial(self._save_desc, r["id"], txt, filtro))
                ll.addWidget(txt); ll.addWidget(btn)
            else:
                lbl = QLabel(desc); lbl.setWordWrap(True); ll.addWidget(lbl)
            card.add_left(left)

            # derecha: editar / abrir / ejecutar
            right = QWidget(); rl = QVBoxLayout(right)
            btn_e = QPushButton("✏️ Editar")
            btn_e.clicked.connect(partial(self._edit, r, filtro))
            rl.addWidget(btn_e)

            ruta = (SCRIPTS_DIR / r["ruta_archivo"]).resolve()
            btn_o = QPushButton("📂 Abrir")
            btn_o.clicked.connect(lambda _, p=ruta: self._open_folder(p))
            rl.addWidget(btn_o)

            btn_r = QPushButton("▶️ Ejecutar")
            btn_r.clicked.connect(lambda _, p=ruta, lg=r["lenguaje"]: self._run(p, lg))
            rl.addWidget(btn_r)

            card.add_right(right)
            self.lay_cards.insertWidget(self.lay_cards.count()-1, card)

    def _save_desc(self, sid: int, txt: QPlainTextEdit, filtro: str) -> None:
        txto = txt.toPlainText().strip()
        if not txto:
            QMessageBox.warning(self, "Error", "La descripción no puede estar vacía.")
            return
        exec_sql("UPDATE Scripts SET descripcion=? WHERE id=?", (txto, sid))
        self._refresh_cards(filtro)

    def _edit(self, row: dict[str, Any], filtro: str) -> None:
        dlg = ScriptDialog(
            self,
            nombre=row["nombre"],
            descripcion=row["descripcion"],
            ruta=str((SCRIPTS_DIR / row["ruta_archivo"]).resolve())
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        nombre, desc, ruta = dlg.data()
        if not nombre or not ruta:
            QMessageBox.warning(self, "Error", "Nombre y ruta obligatorios.")
            return
        rel = get_relative_path_or_copy(ruta, SCRIPTS_DIR, allow_copy=False)
        if rel is None:
            QMessageBox.warning(self, "Error", "La ruta debe estar dentro del proyecto.")
            return
        exec_sql(
            "UPDATE Scripts SET nombre=?,descripcion=?,ruta_archivo=? WHERE id=?",
            (nombre, desc, rel, row["id"])
        )
        self._refresh_cards(self.txt_search.text())

    @staticmethod
    def _run(path: Path, lang: str) -> None:
        if not path.exists():
            QMessageBox.warning(None, "Error", "Archivo no encontrado.")
            return
        cmd_map = {
            "PowerShell": ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(path)],
            "CMD":        ["cmd", "/c", str(path)],
            "Python":     [sys.executable, str(path)],
        }
        cmd = cmd_map.get(lang)
        if not cmd:
            QMessageBox.warning(None, "Error", f"No puedo ejecutar: {lang}")
            return

        flags = 0
        if sys.platform.startswith("win"):
            from subprocess import CREATE_NEW_CONSOLE
            flags = CREATE_NEW_CONSOLE
        subprocess.Popen(cmd, creationflags=flags)

    @staticmethod
    def _open_folder(path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(None, "Error", "Ruta no existe.")
            return
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path.parent)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])