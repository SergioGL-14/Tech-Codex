# The Tech Codex

## Índice

1. [Visión General](#visión-general)
2. [Estructura del Proyecto](#estructura-del-proyecto)
3. [Requisitos e Instalación](#requisitos-e-instalaci%C3%B3n)
4. [Arquitectura y Flujo de Datos](#arquitectura-y-flujo-de-datos)
5. [Ejecución Local y Rutas Confiables](#ejecución-local-y-rutas-confiables)
6. [Módulo Principal: `main.py`](#m%C3%B3dulo-principal-mainpy)
7. [Utilidades Comunes: `utils.py`](#utilidades-comunes-utilspy)
8. [Sistema de Logging](#sistema-de-logging)
9. [Secciones (`sections/`)](#secciones-sections)
   - [Noticias (`news_section.py`)](#noticias-news_sectionpy)
   - [Consejo del Día (`tips_section.py`)](#consejo-del-d%C3%ADa-tips_sectionpy)
   - [Repositorio de Comandos (`commands_section.py`)](#repositorio-de-comandos-commands_sectionpy)
   - [Repositorio de Scripts (`scripts_section.py`)](#repositorio-de-scripts-scripts_sectionpy)
   - [Repositorio de Apps (`apps_section.py`)](#repositorio-de-apps-apps_sectionpy)
   - [Diario de Desarrollo (`diary_section.py`)](#diario-de-desarrollo-diary_sectionpy)
   - [Diario de Incidencias (`incidences_section.py`)](#diario-de-incidencias-incidences_sectionpy)
   - [Documentación (`documentation_section.py`)](#documentaci%C3%B3n-documentation_sectionpy)
10. [Base de Datos](#base-de-datos)
11. [Gestión de Assets y Rutas](#gesti%C3%B3n-de-assets-y-rutas)
12. [Estilo y Temas](#estilo-y-temas)
13. [Manejo de Iconos](#manejo-de-iconos)
14. [Expansión y Personalización](#expansi%C3%B3n-y-personalizaci%C3%B3n)

---

## Visión General

**The Tech Codex** es una aplicación de escritorio multiplataforma (Windows, macOS, Linux), desarrollada en Python 3.10+ con PyQt6 y QtWebEngine. Su misión es ofrecer un "centro de mando" para técnicos informáticos, centralizando:

- Agregador y lector RSS con previsualización embebida.
- Consejos del día organizados y filtrables.
- Repositorios de comandos, scripts y apps portables.
- Diarios de desarrollo e incidencias.
- Documentación local y enlaces externos con editor WYSIWYG.
- Sistema de Logging centralizado.

## Historial de Versiones

| Versión | Fecha       | Cambios principales                                                                                   |
|---------|-------------|-------------------------------------------------------------------------------------------------------|
| 1.0     | 26/04/2025  | Primera versión estable. Integración de todas las secciones y sistema de Logging. |

## Estructura del Proyecto

```text
Tech-Codex/
├── main.py                         # Aplicación y ventana principal
├── utils.py                        # Rutas, SQLite, logging y widgets comunes
├── requirements.txt
├── sections/                       # Módulos de las secciones funcionales
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

En desarrollo, `utils.py` crea automáticamente `database/`, `logs/`, `scripts/`
y `app/` para los datos de la aplicación. No forman parte de la estructura
versionada. En una instalación empaquetada, la base de datos, los logs y los
recursos de usuario se guardan bajo el directorio de datos del usuario.

## Requisitos e Instalación

- **Python 3.10+**
- Dependencias:
  ```bash
   pip install -r requirements.txt
  ```
- Clonar repo y entrar:
  ```bash
  git clone <url>
  cd TheTechCodex
  ```
- Ejecutar:
  ```bash
  python main.py
  ```
- *(Opcional)* Personalizar tema en `ui/estilos.qss`.

## Arquitectura y Flujo de Datos

1. **`main.py`** inicializa la ventana principal y la BD.
2. Menú lateral (`QListWidget`) para secciones.
3. `_switch(idx)` carga dinámicamente el widget de cada sección.
4. Secciones usan `utils.get_conn()` para CRUD en SQLite.
5. Logging de errores en tiempo real a `logs/techcodex.log`.

## Ejecución Local y Rutas Confiables

Los scripts y las aplicaciones se lanzan como procesos locales mediante
`subprocess`; no se ejecutan en un servidor remoto ni dentro de un sandbox.
Solo deben registrarse o seleccionarse archivos y carpetas locales de rutas
confiables, cuyo contenido y origen hayan sido verificados por el usuario.
La aplicación comprueba que la ruta exista, pero no sustituye esa revisión ni
aplica una política de confianza o permisos adicional.

## Módulo Principal: `main.py`

- **`_SCHEMA_SQL`** (en `utils.py`): SQL para crear tablas si faltan.
- **`init_db()`**: arranca BD y activa foreign keys.
- **`excepthook()`**: captura excepciones globales y las manda al logger.
- **`ProcWorker(QObject)`**: ejecuta comandos/procesos en background.
- **`MainWindow`**:
   - `_switch(self, idx)`: cambia de sección.
   - `_run_generic(self, path, lang)`: ejecuta scripts/apps locales.
   - `_open_folder(self, path)`: abre carpetas.


## Utilidades Comunes: `utils.py`

- **Rutas**: `BASE_DIR`, `DB_PATH`, `LOG_PATH`, etc.
- **BD**: `get_conn()`, `fetchone(sql, args)`, `fetchall()`, `exec_sql()`.
- **Files**: `get_relative_path_or_copy(src)`, manejo de assets.
- **UI**: `clear_layout()`, `RepoCard`, `AssetDialog`, `TextEditorDialog`.
- **Iconos**: funciones locales de `diary_section.py` y `documentation_section.py`.


## Sistema de Logging

Todos los errores (scripts, apps, excepciones) se registran en **`logs/techcodex.log`**, ubicando las entradas más recientes al principio:

```text
------- 26/04/2025 00:54 -------
[Python]: utils.py
Traceback (most recent call last):
  File "utils.py", line 42, in get_conn
    conn = sqlite3.connect(DB_PATH)
sqlite3.OperationalError: unable to open database file
```

- **Formato**: `------- DD/MM/YYYY HH:MM -------` en header.
- **Categoría**: `[Python]`, `[Script]`, `[App]`, `[Exception]`, etc.
- **Orden**: nueva entrada insertada arriba.
- **Rotación**: (futura mejora) mantener X MB o X líneas; por ahora sin límite.

## Secciones (`sections/`)

### Noticias (`news_section.py`)
- Configuración de feeds en `NewsCfg`.
- `RSSFetcher(QThread)`: descargas asíncronas.
- `NewsCard`: título, resumen, botones **Ver**, **Leída**, **Favorito**.
- Filtros: origen, texto, fecha, favoritos.

### Consejo del Día (`tips_section.py`)
- Gestión en BD de consejos con **categoría**, **nivel**.
- Navegación: aleatorio o secuencial.
- Atajos: **F** (favorito), **→** (siguiente), **Esc**.

### Repositorio de Comandos (`commands_section.py`)
- CRUD de comandos shell con ejemplos.
- Filtros: texto, estado, favoritos, categoría, lenguaje.
- Botones de marcado rápido.

### Repositorio de Scripts (`scripts_section.py`)
- Añadir/editar/recargar scripts.
- Copia automática a `scripts/`.
- Ejecución oculta (`CREATE_NO_WINDOW`) o en nueva consola.

### Repositorio de Apps (`apps_section.py`)
- Igual que scripts, en `app/`.
- Mapeo extensiones a categorías.
- Ejecución silenciosa o visible.

### Diario de Desarrollo (`diary_section.py`)
- CRUD de proyectos y entradas WYSIWYG.
- Estados: **En curso**, **Pausado**, **Finalizado**.
- Iconos por diario con `_copy_icon()` y `_pixmap()`.

### Diario de Incidencias (`incidences_section.py`)
- CRUD con **prioridad** y **categoría**.
- Filtros y marcado de **resueltas**.

### Documentación (`documentation_section.py`)
- Categorías en BD (`CategorySettings`).
- Grid interactivo de carpetas y enlaces.
- CRUD de archivos locales y URLs.
- Editor HTML WYSIWYG (`FileCreatorDialog`).


## Base de Datos

- **SQLite** con foreign keys activadas.
- Tablas:
  - `DiariosDesarrollo`, `EntradasDesarrollo`, `Incidencias`.
  - `Consejos`, `Comandos`, `Scripts`, `Aplicaciones`.
  - `Documentacion`, `CategorySettings`.

## Esquema de la Base de Datos

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
-- Resto de tablas definidas en utils._SCHEMA_SQL
```
## Gestión de Assets y Rutas

- Rutas relativas desde `BASE_DIR`.
- `get_relative_path_or_copy()` copia recursos externos a carpetas internas.
- Carpeta `icons/<slug>/...` para iconos.

## Estilo y Temas

- Tema Qt **Fusion**.
- Hoja de estilos en `ui/estilos.qss`.
- Sombreados (`QGraphicsDropShadowEffect`) y paletas coherentes.


## Manejo de Iconos

1. Selección con diálogo “…”
2. Validación: `.png`, `.jpg`, `.ico` y ≤2 MB.
3. Copia a `icons/<slug>/...` si viene de fuera.
4. Registro en BD y cache de pixmap a 80×80.


## Expansión y Personalización

- Añadir sección: crear módulo en `sections/`, registrar en `main.py`.
- Ampliar BD: editar `_SCHEMA_SQL` en `utils.py` y migrar.
- Ajustar QSS en `ui/estilos.qss` y feeds en `news_section.py`.

---

## Roadmap

- [ ] Backup y restore automático de la base de datos.
- [ ] Exportación de informes a PDF / CSV desde las distintas secciones.
