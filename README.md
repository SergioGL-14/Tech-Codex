# The Tech Codex

## Index

1. [Overview](#overview)
2. [Project structure](#project-structure)
3. [Requirements and installation](#requirements-and-installation)
4. [Architecture and data flow](#architecture-and-data-flow)
5. [Local execution and trusted paths](#local-execution-and-trusted-paths)
6. [Main module: `main.py`](#main-module-mainpy)
7. [Common utilities: `utils.py`](#common-utilitites-utilspy)
8. [Logging system](#logging-system)
9. [Sections (`sections/`)](#sections-sections)
   - [News (`news_section.py`)](#news-news_sectionpy)
   - [Tip of the day (`tips_section.py`)](#tip-of-the-day-tips_sectionpy)
   - [Command repository (`commands_section.py`)](#command-repository-commands_sectionpy)
   - [Script repository (`scripts_section.py`)](#script-repository-scripts_sectionpy)
   - [App repository (`apps_section.py`)](#app-repository-apps_sectionpy)
   - [Development diary (`diary_section.py`)](#development-diary-diary_sectionpy)
   - [Incident diary (`incidences_section.py`)](#incident-diary-incidences_sectionpy)
   - [Documentation (`documentation_section.py`)](#documentation-documentation_sectionpy)
10. [Database](#database)
11. [Asset and path handling](#asset-and-path-handling)
12. [Style and themes](#style-and-themes)
13. [Icon handling](#icon-handling)
14. [Extension and customization](#extension-and-customization)

---

## Overview

**The Tech Codex** is a cross-platform desktop application (Windows, macOS,
Linux) written in Python 3.10+ with PyQt6 and QtWebEngine. Its mission is to
be a "command center" for IT technicians, centralizing:

- RSS aggregator and reader with embedded preview.
- Daily tips, organized and filterable.
- Repositories of commands, scripts and portable apps.
- Development and incident diaries.
- Local documentation and external links with a WYSIWYG editor.
- Centralized logging system.

## Version history

| Version | Date       | Main changes |
|---------|------------|--------------|
| 1.0     | 26/04/2025 | First stable release. All sections integrated plus the logging system. |

## Project structure

```text
Tech-Codex/
├── main.py                         # Application and main window
├── utils.py                        # Paths, SQLite, logging, common widgets
├── requirements.txt
├── sections/                       # Functional section modules
│   ├── about_section.py
│   ├── apps_section.py
│   ├── commands_section.py
│   ├── diary_section.py
│   ├── documentation_section.py
│   ├── editor_section.py
│   ├── incidences_section.py
│   ├── news_section.py
│   ├── scripts_section.py
│   └── tips_section.py
├── ui/estilos.qss
├── about.md
├── LICENSE
└── README.md
```

During development, `utils.py` automatically creates `database/`, `logs/`,
`scripts/` and `app/` for application data. They are not part of the
versioned tree. In a packaged install, database, logs and user assets live
under the user data directory.

## Requirements and installation

- **Python 3.10+**
- Dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- Clone the repo and enter it:
  ```bash
  git clone https://github.com/SergioGL-14/Tech-Codex.git
  cd Tech-Codex
  ```
- Run:
  ```bash
  python main.py
  ```
- *(Optional)* Customize the theme in `ui/estilos.qss`.

## Architecture and data flow

1. **`main.py`** initializes the main window and the DB.
2. Side menu (`QListWidget`) for sections.
3. `_switch(idx)` dynamically loads each section's widget.
4. Sections use `utils.get_conn()` for SQLite CRUD.
5. Errors log in real time to `logs/techcodex.log`.

## Local execution and trusted paths

Scripts and apps are launched as local processes through `subprocess`; they
do not run on a remote server or inside a sandbox. Only register or select
files and folders from trusted paths whose content and origin have been
verified by you. The app checks that the path exists, but that check is no
substitute for your review — no additional trust policy or permissions are
applied.

## Main module: `main.py`

- **`_SCHEMA_SQL`** (in `utils.py`): SQL that creates missing tables.
- **`init_db()`**: boots the DB and enables foreign keys.
- **`excepthook()`**: catches global exceptions and sends them to the logger.
- **`ProcWorker(QObject)`**: runs commands/processes in the background.
- **`MainWindow`**:
   - `_switch(self, idx)`: switches section.
   - `_run_generic(self, path, lang)`: runs local scripts/apps.
   - `_open_folder(self, path)`: opens folders.


## Common utilities: `utils.py`

- **Paths**: `BASE_DIR`, `DB_PATH`, `LOG_PATH`, etc.
- **DB**: `get_conn()`, `fetchone(sql, args)`, `fetchall()`, `exec_sql()`.
- **Files**: `get_relative_path_or_copy(src)`, asset handling.
- **UI**: `clear_layout()`, `RepoCard`, `AssetDialog`, `TextEditorDialog`.
- **Icons**: local helpers in `diary_section.py` and `documentation_section.py`.


## Logging system

Every error (scripts, apps, exceptions) is recorded in
**`logs/techcodex.log`**, newest entries at the top:

```text
------- 26/04/2025 00:54 -------
[Python]: utils.py
Traceback (most recent call last):
  File "utils.py", line 42, in get_conn
    conn = sqlite3.connect(DB_PATH)
sqlite3.OperationalError: unable to open database file
```

- **Format**: `------- DD/MM/YYYY HH:MM -------` header.
- **Category**: `[Python]`, `[Script]`, `[App]`, `[Exception]`, etc.
- **Order**: new entries inserted at the top.
- **Rotation**: (future improvement) cap by size or lines; currently unlimited.

## Sections (`sections/`)

### News (`news_section.py`)
- Feed configuration in `NewsCfg`.
- `RSSFetcher(QThread)`: async downloads.
- `NewsCard`: title, summary, buttons **Ver**, **Leída**, **Favorito**.
- Filters: source, text, date, favorites.

### Tip of the day (`tips_section.py`)
- Tips stored in the DB with **category** and **level**.
- Navigation: random or sequential.
- Shortcuts: **F** (favorite), **→** (next), **Esc**.

### Command repository (`commands_section.py`)
- CRUD for shell commands with examples.
- Filters: text, status, favorites, category, language.
- Quick-flag buttons.

### Script repository (`scripts_section.py`)
- Add/edit/reload scripts.
- Automatic copy into `scripts/`.
- Hidden execution (`CREATE_NO_WINDOW`) or in a new console.

### App repository (`apps_section.py`)
- Same as scripts, under `app/`.
- Extension-to-category mapping.
- Silent or visible execution.

### Development diary (`diary_section.py`)
- CRUD for projects and WYSIWYG entries.
- Statuses: **En curso**, **Pausado**, **Finalizado**.
- Per-diary icons with `_copy_icon()` and `_pixmap()`.

### Incident diary (`incidences_section.py`)
- CRUD with **priority** and **category**.
- Filters and marking of **resolved** incidents.

### Documentation (`documentation_section.py`)
- Categories stored in the DB (`CategorySettings`).
- Interactive grid of folders and links.
- CRUD for local files and URLs.
- WYSIWYG HTML editor (`FileCreatorDialog`).


## Database

- **SQLite** with foreign keys enabled.
- Tables:
  - `DiariosDesarrollo`, `EntradasDesarrollo`, `Incidencias`.
  - `Consejos`, `Comandos`, `Scripts`, `Aplicaciones`.
  - `Documentacion`, `CategorySettings`.

## Database schema

```sql
CREATE TABLE IF NOT EXISTS DiariosDesarrollo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT UNIQUE NOT NULL,
    descripcion TEXT,
    fecha_creacion TEXT NOT NULL,
    lenguaje TEXT,
    estado TEXT DEFAULT 'En curso',
    icono  TEXT
);
-- Remaining tables defined in utils._SCHEMA_SQL
```
## Asset and path handling

- Relative paths from `BASE_DIR`.
- `get_relative_path_or_copy()` copies external assets into internal folders.
- Folder `icons/<slug>/...` for icons.

## Style and themes

- Qt **Fusion** style.
- Stylesheet in `ui/estilos.qss`.
- Drop shadows (`QGraphicsDropShadowEffect`) and a coherent palette.


## Icon handling

1. Selection via the “…” dialog
2. Validation: `.png`, `.jpg`, `.ico`, ≤2 MB.
3. Copy to `icons/<slug>/...` when coming from outside.
4. Stored in the DB and pixmap cache at 80×80.


## Extension and customization

- Add a section: create a module in `sections/`, register it in `main.py`.
- Extend the DB: edit `_SCHEMA_SQL` in `utils.py` and migrate.
- Tweak QSS in `ui/estilos.qss` and feeds in `news_section.py`.

Next candidates when the app needs them: automatic database backup/restore
and PDF/CSV report export from the different sections.

---

UI labels quoted above (**Ver**, **En curso**, …) appear as the interface
shows them, which is in Spanish.
