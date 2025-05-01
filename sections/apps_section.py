# sections/apps_section.py
# Repositorio de Aplicaciones — búsqueda, CRUD, copia automática
# y ejecución silenciosa (sin consola) en Windows)
# Refactor 26-abr-2025
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from functools import partial
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMessageBox,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QWidget,
)

from utils import (
    RepoCard,
    AssetDialog,
    clear_layout,
    exec_sql,
    fetchall,
    get_conn,
    get_relative_path_or_copy,
)

__all__ = ["AppsSection"]


# ═════════════  Sección Apps  ═════════════
class AppsSection(QWidget):
    """
    Repositorio local de aplicaciones / script-apps.

    • Todo se almacena con rutas **relativas** a ``self.base_dir`` → portabilidad  
    • «Recargar» inspecciona ``self.base_dir`` y registra carpetas no listadas.  
    • «Añadir» permite escoger un .exe / .ps1 / .bat / .py (u otra carpeta);
      si está fuera del directorio de datos, se copia a ``self.base_dir``.
    """

    def __init__(
        self,
        base_dir: Path,             # …/app en DATA_DIR
        ext_map: dict[str, str],    # {".exe": "EXE", ".ps1": "PowerShell", …}
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.base_dir = base_dir
        self.ext_map  = ext_map
        self._build_ui()
        self._refresh_cards("")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ░░ barra superior
        bar = QHBoxLayout()
        self.txt_search = QLineEdit(placeholderText="Buscar…")
        btn_add    = QPushButton("➕ Añadir")
        btn_reload = QPushButton("🔄 Recargar")

        bar.addWidget(QLabel("Buscar:")); bar.addWidget(self.txt_search)
        bar.addStretch()
        bar.addWidget(btn_add); bar.addWidget(btn_reload)
        root.addLayout(bar)

        # ░░ área de tarjetas
        self.scroll = QScrollArea(widgetResizable=True)
        self.container = QWidget()
        self.lay_cards = QVBoxLayout(self.container)
        self.lay_cards.setContentsMargins(0, 0, 0, 0)
        self.lay_cards.setSpacing(10)
        self.lay_cards.addStretch()
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll)

        # ░░ señales
        self.txt_search.textChanged.connect(lambda txt: self._refresh_cards(txt))
        btn_add.clicked.connect(self._on_add)
        btn_reload.clicked.connect(self._on_reload)

    def _refresh_cards(self, filtro: str) -> None:
        """Recarga tarjetas aplicando filtro por nombre."""
        # mantener stretch final
        stretch = self.lay_cards.takeAt(self.lay_cards.count() - 1)
        clear_layout(self.lay_cards)
        self.lay_cards.addItem(stretch)

        filtro = filtro.lower()
        for row in fetchall("SELECT * FROM Aplicaciones ORDER BY nombre"):
            if filtro and filtro not in row["nombre"].lower():
                continue

            card = RepoCard(row["nombre"])

            # — izquierda: descripción editable —
            left = QWidget(); ll = QVBoxLayout(left)
            desc = row["descripcion"] or ""
            if not desc.strip() or desc.startswith("Sin descripción"):
                txt_desc = QPlainTextEdit(desc)
                btn_save = QPushButton("Guardar")
                btn_save.clicked.connect(
                    partial(self._save_desc, row["id"], txt_desc, filtro)
                )
                ll.addWidget(txt_desc); ll.addWidget(btn_save)
            else:
                lbl = QLabel(desc); lbl.setWordWrap(True); ll.addWidget(lbl)
            card.add_left(left)

            # — derecha: acciones —
            right = QWidget(); rl = QVBoxLayout(right)
            btn_edit = QPushButton("✏️ Editar")
            btn_edit.clicked.connect(partial(self._on_edit, row, filtro))
            rl.addWidget(btn_edit)

            ruta_abs = (self.base_dir / row["ruta_principal"]).resolve()

            btn_open = QPushButton("📂 Abrir")
            btn_open.clicked.connect(lambda _, p=ruta_abs: self._open_folder(p))
            rl.addWidget(btn_open)

            btn_run = QPushButton("▶️ Ejecutar")
            btn_run.clicked.connect(
                lambda _, p=ruta_abs, lang=row["lenguaje"]: self._run_generic(p, lang)
            )
            rl.addWidget(btn_run)

            card.add_right(right)
            # insertar antes del stretch
            self.lay_cards.insertWidget(self.lay_cards.count() - 1, card)

    def _on_add(self) -> None:
        dlg = AssetDialog(self, title="", descripcion="", ruta="",
                          mode="Añadir", type_name="Aplicación")
        if dlg.exec() != dlg.DialogCode.Accepted:
            return

        d = dlg.data()
        src = Path(d["ruta"])
        if not src.exists():
            QMessageBox.warning(self, "Ruta", "Archivo o carpeta no existe.")
            return

        # copia dentro de self.base_dir si está fuera
        rel = get_relative_path_or_copy(str(src), self.base_dir, allow_copy=True)
        if rel is None:
            QMessageBox.warning(self, "Error", "No se pudo copiar/relativizar la ruta.")
            return

        lang   = self.ext_map.get(src.suffix.lower(), "Otro") if src.is_file() else "Otro"
        nombre = d["nombre"] or src.stem
        try:
            exec_sql(
                "INSERT INTO Aplicaciones(nombre,descripcion,lenguaje,ruta_principal) "
                "VALUES(?,?,?,?)",
                (nombre, d["descripcion"], lang, rel),
            )
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Duplicado", "Ya existe una aplicación con ese nombre.")
            return

        self._refresh_cards(self.txt_search.text())

    def _on_reload(self) -> None:
        """Escanea self.base_dir y registra las nuevas carpetas."""
        self.base_dir.mkdir(exist_ok=True)
        added = 0

        with get_conn() as conn:
            cur = conn.cursor()
            for folder in self.base_dir.iterdir():
                if not folder.is_dir():
                    continue
                # fichero principal = <folder>/<folder>.<ext>
                for ext, lang in self.ext_map.items():
                    main = folder / f"{folder.name}{ext}"
                    if main.exists():
                        rel = main.relative_to(self.base_dir).as_posix()
                        try:
                            cur.execute(
                                "INSERT INTO Aplicaciones(nombre,descripcion,lenguaje,ruta_principal) "
                                "VALUES(?, 'Sin descripción', ?, ?)",
                                (folder.name, lang, rel),
                            )
                            added += 1
                        except sqlite3.IntegrityError:
                            pass
                        break
            conn.commit()

        QMessageBox.information(self, "Recarga", f"Añadidas {added} aplicación(es).")
        self._refresh_cards(self.txt_search.text())

    def _on_edit(self, row: dict[str, Any], filtro: str) -> None:
        dlg = AssetDialog(
            self,
            title=row["nombre"],
            descripcion=row["descripcion"],
            ruta=str((self.base_dir / row["ruta_principal"]).resolve()),
            mode="Editar",
            type_name="Aplicación",
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            return

        data = dlg.data()
        src = Path(data["ruta"])
        if not src.exists():
            QMessageBox.warning(self, "Ruta", "Archivo no existe.")
            return

        rel = get_relative_path_or_copy(str(src), self.base_dir, allow_copy=False)
        if rel is None:
            QMessageBox.warning(self, "Ruta", "La ruta debe estar dentro del directorio de datos.")
            return

        lang = self.ext_map.get(src.suffix.lower(), "Otro") if src.is_file() else "Otro"
        exec_sql(
            "UPDATE Aplicaciones SET nombre=?,descripcion=?,lenguaje=?,ruta_principal=? WHERE id=?",
            (data["nombre"], data["descripcion"], lang, rel, row["id"]),
        )
        self._refresh_cards(filtro)

    def _save_desc(self, app_id: int, txt: QPlainTextEdit, filtro: str) -> None:
        desc = txt.toPlainText().strip()
        if not desc:
            QMessageBox.warning(self, "Vacío", "La descripción no puede estar vacía.")
            return
        exec_sql("UPDATE Aplicaciones SET descripcion=? WHERE id=?", (desc, app_id))
        self._refresh_cards(filtro)

    @staticmethod
    def _run_generic(path: Path, lang: str) -> None:
        if not path.exists():
            QMessageBox.warning(None, "Ruta", "Archivo no encontrado.")
            return

        flags = 0
        if sys.platform.startswith("win"):
            from subprocess import CREATE_NO_WINDOW  # type: ignore
            flags = CREATE_NO_WINDOW

        if lang == "EXE":
            subprocess.Popen([str(path)], creationflags=flags)  # noqa: S603
            return

        cmd_map = {
            "PowerShell": ["powershell", "-ExecutionPolicy", "Bypass",
                           "-NoProfile", "-WindowStyle", "Hidden", "-File", str(path)],
            "CMD":   ["cmd", "/c", str(path)],
            "BAT":   ["cmd", "/c", str(path)],
            "Python": [sys.executable, str(path)],
        }
        cmd = cmd_map.get(lang)
        if not cmd:
            QMessageBox.warning(None, "Lenguaje", f"No se puede ejecutar archivos de tipo {lang}")
            return

        subprocess.Popen(cmd, creationflags=flags)  # noqa: S603

    @staticmethod
    def _open_folder(file_path: Path) -> None:
        if not file_path.exists():
            QMessageBox.warning(None, "Ruta", "La ruta no existe.")
            return

        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(file_path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "--", str(file_path.parent)])
        else:
            subprocess.Popen(["xdg-open", str(file_path.parent)])