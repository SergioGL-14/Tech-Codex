#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils.py · The Tech Codex
Helpers for paths, database, UI components and cross-cutting utilities.
"""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence
import sys
import os

from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
    QDialog,
    QDialogButtonBox,
    QSizePolicy,
)


BASE_DIR = Path(__file__).resolve().parent

def resource_path(*relative_parts: str) -> Path:
    """
    Returns the absolute path to a bundled resource.
    - In a PyInstaller bundle it uses sys._MEIPASS.
    - In development it uses the folder where this utils.py lives.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        # use this utils.py's own folder directly
        base = Path(__file__).resolve().parent
    return base.joinpath(*relative_parts)

# ╔═════════════════════  Basic paths  ═════════════════════╗

# ── Persistent data directory (DB, logs, config) ──────
if getattr(sys, "frozen", False):
    # When packaged with PyInstaller
    if sys.platform.startswith("win"):
        DATA_DIR = Path(os.getenv("LOCALAPPDATA",
                                   Path.home() / "AppData" / "Local")) / "TheTechCodex"
    else:
        DATA_DIR = Path.home() / ".local" / "share" / "TheTechCodex"
else:
    # In development, we use the project folder
    DATA_DIR = BASE_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_DIR  = DATA_DIR / "database"; DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "techcodex.db"

DOCS_DIR    = BASE_DIR / "docs";    DOCS_DIR.mkdir(exist_ok=True)
SCRIPTS_DIR = DATA_DIR / "scripts"; SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
APPS_DIR    = DATA_DIR / "app";     APPS_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_EXT = {".ps1": "PowerShell", ".py": "Python", ".bat": "CMD", ".cmd": "CMD"}
APP_EXT    = {**SCRIPT_EXT, **{".exe": "EXE"}}

LOG_DIR  = DATA_DIR / "logs"; LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / "techcodex.log"


# ╔═══════════════  SQL schema (simple migration)  ═════════════════╗
_SCHEMA_SQL: str = """
CREATE TABLE IF NOT EXISTS DiariosDesarrollo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT UNIQUE NOT NULL,
    descripcion TEXT,
    fecha_creacion TEXT NOT NULL,
    lenguaje TEXT,
    estado TEXT DEFAULT 'En curso',
    icono  TEXT
);
CREATE TABLE IF NOT EXISTS Consejos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT NOT NULL,
    categoria TEXT,
    nivel TEXT,
    codigo_ejemplo TEXT,
    estado TEXT DEFAULT 'Pendiente',
    favorito BOOLEAN DEFAULT 0,
    fecha_aprendido TEXT
);
CREATE TABLE IF NOT EXISTS EntradasDesarrollo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_diario INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    fecha TEXT NOT NULL,
    contenido TEXT NOT NULL,
    FOREIGN KEY(id_diario) REFERENCES DiariosDesarrollo(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS Comandos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT NOT NULL,
    codigo_ejemplo TEXT NOT NULL,
    estado TEXT DEFAULT 'Pendiente',
    favorito INTEGER DEFAULT 0,
    fecha_aprendido TEXT,
    categoria_funcional TEXT,
    lenguaje TEXT
);
CREATE TABLE IF NOT EXISTS Scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE,
    descripcion TEXT,
    lenguaje TEXT,
    ruta_archivo TEXT
);
CREATE TABLE IF NOT EXISTS Aplicaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE,
    descripcion TEXT,
    lenguaje TEXT,
    ruta_principal TEXT
);
CREATE TABLE IF NOT EXISTS Incidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    fecha TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    solucion TEXT,
    estado TEXT DEFAULT 'Pendiente',
    prioridad TEXT,
    categoria TEXT
);
CREATE TABLE IF NOT EXISTS Documentacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL,
    titulo TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK(tipo IN ('Local','Externo')),
    ruta TEXT NOT NULL,
    descripcion TEXT,
    UNIQUE (categoria, titulo)
);
"""

def init_db() -> None:
    """Initializes (or migrates) the database."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

# ╔═══════════════════  Data access  ════════════════════════════╗
@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Safe context with FK and WAL; row_factory → dict."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def fetchone(query: str, params: Sequence[Any] | None = None) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(query, params or []).fetchone()
        return dict(row) if row else None

def fetchall(query: str, params: Sequence[Any] | None = None) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params or []).fetchall()]

def exec_sql(query: str, params: Sequence[Any] | None = None) -> None:
    with get_conn() as conn:
        conn.execute(query, params or [])
        conn.commit()

# ╔══════════════════  Layout helpers  ══════════════════════════╗
def clear_layout(layout) -> None:
    """Recursively empties a QLayout (widgets, sub-layouts and spacers)."""
    while layout.count():
        item = layout.takeAt(0)
        if item.layout():
            clear_layout(item.layout())
            item.layout().deleteLater()
        elif item.widget():
            item.widget().deleteLater()
        elif isinstance(item, QSpacerItem):
            pass

# ╔══════════════════  File management  ════════════════════════╗
def get_relative_path_or_copy(src: str, base: Path, *, allow_copy: bool = False) -> Optional[str]:
    """
    If *src* is already inside *base* → returns the relative path.
    Si no y `allow_copy=True` → copia a *base* y devuelve nueva ruta relativa.
    Devuelve `None` si falla.
    """
    src_p, base_p = Path(src).resolve(), base.resolve()
    try:
        return src_p.relative_to(base_p).as_posix()
    except ValueError:
        if not allow_copy:
            return None
        dest = base_p / src_p.name
        try:
            if src_p.is_dir():
                shutil.copytree(src_p, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(src_p, dest)
            return dest.relative_to(base_p).as_posix()
        except (OSError, shutil.Error):
            return None

# ╔══════════════════════  Error logging  ═════════════════════╗        
def log_execution_error(error_msg: str, file_path: str, lenguaje: str = "") -> None:
    """
    Logs an execution error to logs/techcodex.log with format:
    ------- DD/MM/YYYY HH:MM -------
    [Type/Language]: Path of the file/script
    Error description
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    header = f"------- {timestamp} -------\n"
    lang_info = f"[{lenguaje}] " if lenguaje else ""
    body = f"{lang_info}{file_path}\n{error_msg.strip()}\n\n"

    new_entry = header + body

    try:
        if LOG_PATH.exists():
            existing = LOG_PATH.read_text(encoding="utf-8")
        else:
            existing = ""
        LOG_PATH.write_text(new_entry + existing, encoding="utf-8")
    except Exception as e:
        print(f"ERROR al escribir en el log: {e}")

# ╔═══════════════  Generic UI components  ══════════════════════╗
class RepoCard(QGroupBox):
    """Horizontal card with shadow; used in Scripts / Apps."""

    def __init__(self, title: str = "") -> None:
        super().__init__(title)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=12, xOffset=2, yOffset=2))
        self.lay = QHBoxLayout(self)

    def add_left(self, w: QWidget) -> None:
        self.lay.addWidget(w, 1)

    def add_right(self, w: QWidget) -> None:
        self.lay.addWidget(w, 0)


class AssetDialog(QDialog):
    """
    Create / edit an asset (Script or Application).
    Fields: name, description, path (browse button).
    """

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str = "",
        descripcion: str = "",
        ruta: str = "",
        mode: str = "Añadir",
        type_name: str = "Script",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{mode} {type_name}")
        self.resize(500, 300)

        form = QFormLayout(self)

        self.txt_nombre = QLineEdit(title)
        self.txt_desc   = QPlainTextEdit(descripcion, maximumHeight=80)

        # path field + browse button
        h = QHBoxLayout()
        self.txt_ruta = QLineEdit(ruta)
        btn_browse = QPushButton("…")
        btn_browse.clicked.connect(self._browse)
        h.addWidget(self.txt_ruta, 1)
        h.addWidget(btn_browse)

        ruta_w = QWidget(); ruta_w.setLayout(h)

        form.addRow("Título / nombre:", self.txt_nombre)
        form.addRow("Descripción:", self.txt_desc)
        form.addRow("Ruta ejecutable:", ruta_w)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addWidget(bb)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo")
        if not path:
            path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if path:
            self.txt_ruta.setText(path)

    def data(self) -> dict[str, str]:
        return {
            "nombre":      self.txt_nombre.text().strip(),
            "descripcion": self.txt_desc.toPlainText().strip(),
            "ruta":        self.txt_ruta.text().strip(),
        }
