#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The Tech Codex — Lanzador principal
Autor: Sergio · Actualizado 2025-04-25
"""

from __future__ import annotations

# 1) Inicializar Qt WebEngine (importación temprana)
from PyQt6 import QtWebEngineWidgets

import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Callable
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication, QGraphicsDropShadowEffect, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QPlainTextEdit, QSizePolicy, QVBoxLayout, QWidget,
)

# ── utilidades y rutas ──────────────────────────────────────────────
from utils import (
    resource_path,
    DB_PATH, SCRIPTS_DIR, APPS_DIR, APP_EXT,
    clear_layout, init_db, log_execution_error
)

# ── secciones ───────────────────────────────────────────────────────
from sections.news_section          import NewsSection
from sections.tips_section          import TipsSection
from sections.commands_section      import CommandsSection
from sections.scripts_section       import ScriptsSection
from sections.apps_section          import AppsSection
from sections.diary_section         import DiarySection
from sections.incidences_section    import IncidenciasSection
from sections.documentation_section import DocumentationSection
from sections.about_section         import AboutSection
from sections.github_section        import GitHubSection
from sections.gdrive_section        import GDriveSection
from sections.onedrive_section      import OneDriveSection

# ── Help para capturar excepciones no atrapadas ─────────────────────
def excepthook(exc_type, exc_value, exc_tb):
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(msg, file=sys.stderr)
    log_execution_error(msg, "Excepción no atrapada en ejecución global", "PYTHON")
    QMessageBox.critical(None, "Error inesperado", msg)
    sys.exit(1)

# ── Worker para procesos externos ───────────────────────────────────
class ProcWorker(QObject):
    finished = pyqtSignal(str)

    def __init__(self, cmd: list[str]) -> None:
        super().__init__()
        self.cmd = cmd

    def run(self) -> None:
        try:
            res = subprocess.run(self.cmd, capture_output=True, text=True)
            output = res.stdout.strip() or res.stderr.strip() or "(Sin salida)"
            if res.returncode != 0:
                log_execution_error(output, " ".join(self.cmd),
                                    lenguaje=self._detect_language())
        except Exception as exc:
            error_msg = f"ERROR: {exc}"
            log_execution_error(error_msg, " ".join(self.cmd),
                                lenguaje=self._detect_language())
            output = error_msg
        self.finished.emit(output)

    def _detect_language(self) -> str:
        lower = self.cmd[0].lower()
        if "powershell" in lower: return "PowerShell"
        if "cmd" in lower:        return "CMD"
        if "python" in lower:     return "Python"
        if ".exe" in lower:       return "EXE"
        return "Otro"

# ── Ventana principal ───────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("The Tech Codex")
        self.resize(1280, 830)

        # Icono de la aplicación
        ico = resource_path("icons", "app_icon.ico")
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))

        central = QWidget(self)
        root = QHBoxLayout(central)
        self.setCentralWidget(central)

        # menú lateral
        self.menu = QListWidget()
        self.menu.setMinimumWidth(200)
        self.menu.setSpacing(3)
        self.menu.setStyleSheet("""
            QListWidget { font-size: 12px; }
            QListWidget::item { padding: 6px 8px; }
        """)
        self._populate_menu()
        self.menu.currentRowChanged.connect(self._switch)

        # contenedor central
        self.stack = QWidget()
        self.stack_lay = QVBoxLayout(self.stack)
        self.stack_lay.setContentsMargins(20, 20, 20, 20)
        self.stack_lay.setSpacing(15)
        self.stack_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        root.addWidget(self.menu, 1)
        root.addWidget(self.stack, 4)

        self._threads: list[QThread] = []
        self._switch(self.menu.currentRow())

    def _add_header(self, title: str) -> None:
        item = QListWidgetItem(title)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = QFont(); font.setBold(True); font.setPointSize(11)
        item.setFont(font)
        item.setBackground(QColor(45, 45, 45))
        hint = item.sizeHint()
        item.setSizeHint(QSize(hint.width(), hint.height() + 10))
        self.menu.addItem(item)

    def _add_entry(self, emoji: str, title: str) -> None:
        item = QListWidgetItem(f"   {emoji}  {title}")
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.menu.addItem(item)

    def _populate_menu(self) -> None:
        self._add_header("Inicio")
        self._add_entry("📰", "Noticias")
        self._add_entry("💡", "Consejo del Día")

        self._add_header("Repositorios")
        self._add_entry("⌨️", "Repo. de Comandos")
        self._add_entry("📝", "Repositorio de Scripts")
        self._add_entry("💻", "Repositorio de Apps")

        self._add_header("Diarios")
        self._add_entry("✏️", "Diario de Desarrollo")
        self._add_entry("🚨", "Diario de Incidencias")

        self._add_header("Información")
        self._add_entry("📖", "Documentación")
        self._add_entry("ℹ️", "Acerca De")

        self._add_header("Integraciones")
        self._add_entry("🐙", "GitHub")
        self._add_entry("☁️", "Google Drive")
        self._add_entry("📂", "OneDrive")

    def _switch(self, idx: int) -> None:
        if idx < 0: return
        clear_layout(self.stack_lay)

        mapping: dict[int, type[QWidget]] = {}
        row = 0
        for text, cls in [
            ("📰  Noticias", NewsSection),
            ("💡  Consejo del Día", TipsSection),
            ("⌨️  Repo. de Comandos", CommandsSection),
            ("📝  Repositorio de Scripts", ScriptsSection),
            ("💻  Repositorio de Apps", AppsSection),
            ("✏️  Diario de Desarrollo", DiarySection),
            ("🚨  Diario de Incidencias", IncidenciasSection),
            ("📖  Documentación", DocumentationSection),
            ("ℹ️  Acerca De", AboutSection),
            ("🐙  GitHub", GitHubSection),
            ("☁️  Google Drive", GDriveSection),
            ("📂  OneDrive", OneDriveSection),
        ]:
            while row < self.menu.count():
                itm = self.menu.item(row)
                if itm.text().strip() == text:
                    mapping[row] = cls
                    row += 1
                    break
                row += 1

        cls = mapping.get(idx)
        if cls:
            # Repositorio de Apps necesita dos parámetros
            if cls is AppsSection:
                widget = cls(APPS_DIR, APP_EXT)
            # Secciones sin argumentos
            elif cls in (DocumentationSection, AboutSection, NewsSection, GitHubSection, GDriveSection, OneDriveSection):
                widget = cls()
            # El resto de secciones toman la BD como parámetro
            else:
                widget = cls(DB_PATH)

            self.stack_lay.addWidget(widget)
        else:
            itm = self.menu.item(idx)
            name = itm.text().strip() if itm else f"Ítem {idx}"
            lbl = QLabel(f"Sección en construcción: {name}")
            lbl.setStyleSheet("font-style: italic; color: #999;")
            self.stack_lay.addWidget(lbl)

    def _run_background(self, cmd: list[str]) -> None:
        thread = QThread(self)
        worker = ProcWorker(cmd)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def on_done(out: str, th: QThread = thread) -> None:
            QMessageBox.information(self, "Salida", out)
            th.quit(); th.wait()
            self._threads.remove(th)

        worker.finished.connect(on_done)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()
        self._threads.append(thread)

    def _run_generic(self, path: Path | None, lang: str) -> None:
        if not path or not path.exists():
            QMessageBox.warning(self, "Ruta", "Archivo no encontrado")
            return

        try:
            is_script = path.resolve().is_relative_to(SCRIPTS_DIR.resolve())
        except Exception:
            is_script = SCRIPTS_DIR.resolve() in path.resolve().parents

        cmd_map = {
            "PowerShell": ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(path)],
            "CMD":        ["cmd", "/k", str(path)],
            "Python":     [sys.executable, str(path)],
        }
        cmd = cmd_map.get(lang)

        if lang == "EXE":
            try:
                subprocess.Popen([str(path)], creationflags=0)
            except Exception as e:
                log_execution_error(str(e), str(path), lenguaje="EXE")
                QMessageBox.critical(self, "Error de ejecución", f"No se pudo lanzar:\n{e}")
            return

        if not cmd:
            QMessageBox.warning(self, "Lenguaje", f"No se puede ejecutar: {lang}")
            return

        flags = 0
        if sys.platform.startswith("win"):
            from subprocess import CREATE_NEW_CONSOLE, CREATE_NO_WINDOW
            flags = CREATE_NEW_CONSOLE if is_script else CREATE_NO_WINDOW

        try:
            subprocess.Popen(cmd, creationflags=flags)
        except Exception as e:
            log_execution_error(str(e), str(path), lenguaje=lang)
            QMessageBox.critical(self, "Error de ejecución", f"No se pudo lanzar:\n{e}")

    @staticmethod
    def _open_folder(path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], check=False)
        else:
            subprocess.Popen(["xdg-open", str(path)], check=False)

def main() -> None:
    init_db()
    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    icon_path = BASE_DIR / "icons" / "TechCodex.ico"
    app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyle("Fusion")

    # Carga de estilos QSS
    qss = resource_path("ui", "estilos.qss")
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
