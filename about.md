# The Tech Codex

## Índice

1. [Visión General](#visión-general)
2. [Estructura del Proyecto](#estructura-del-proyecto)
3. [Requisitos e Instalación](#requisitos-e-instalaci%C3%B3n)
4. [Arquitectura y Flujo de Datos](#arquitectura-y-flujo-de-datos)
5. [Módulo Principal: `main.py`](#m%C3%B3dulo-principal-mainpy)
6. [Utilidades Comunes: `utils.py`](#utilidades-comunes-utilspy)
7. [Sistema de Logging](#sistema-de-logging)
8. [Secciones (`sections/`)](#secciones-sections)
   - [Noticias (`news_section.py`)](#noticias-news_sectionpy)
   - [Consejo del Día (`tips_section.py`)](#consejo-del-d%C3%ADa-tips_sectionpy)
   - [Repositorio de Comandos (`commands_section.py`)](#repositorio-de-comandos-commands_sectionpy)
   - [Repositorio de Scripts (`scripts_section.py`)](#repositorio-de-scripts-scripts_sectionpy)
   - [Repositorio de Apps (`apps_section.py`)](#repositorio-de-apps-apps_sectionpy)
   - [Diario de Desarrollo (`diary_section.py`)](#diario-de-desarrollo-diary_sectionpy)
   - [Diario de Incidencias (`incidences_section.py`)](#diario-de-incidencias-incidences_sectionpy)
   - [Documentación (`documentation_section.py`)](#documentaci%C3%B3n-documentation_sectionpy)
   - [GitHub (`github_section.py`)](#github-github_sectionpy)
9. [Integraciónes](#integraci%C3%B3n-con-github)
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
- Integración completa con GitHub.

## Historial de Versiones

| Versión | Fecha       | Cambios principales                                                                                   |
|---------|-------------|-------------------------------------------------------------------------------------------------------|
| 1.0     | 26/04/2025  | Primera versión estable. Integración de todas las secciones, sistema de Logging e integración GitHub. |

## Estructura del Proyecto

```bash
TheTechCodex/
├── main.py
├── utils.py
├── database/             
│   ├── techcodex.bd          # techcodex.db (SQLite)
│   ├── config.json           # Token GitHub y prefs
│   ├── .csv                  # Csv con Datos
├── ui/                   # estilos.qss
├── sections/             # news, tips, commands, scripts, apps, diary, incidences, documentation, github
│   ├── news_section.py
│   ├── tips_section.py
│   ├── commands_section.py
│   ├── scripts_section.py
│   ├── apps_section.py
│   ├── diary_section.py
│   ├── incidences_section.py
│   ├── gdrive_section.py
│   ├── onedrive_section.py
│   ├── documentation_section.py
│   └── github_section.py
├── logs/                 # techcodex.log
├── docs/                 # Documentación local
├── repos/                # Repositorios de GitHub
├── scripts/              # Scripts portables del usuario
├── app/                  # Aplicaciones portables añadidas
├── icons/                # Iconos personalizados
└── README.md
```

## Requisitos e Instalación

- **Python 3.10+**
- Dependencias:
  ```bash
  pip install PyQt6 PyQt6-WebEngine feedparser requests pygithub
  ```
- Clonar repo y entrar:
  ```bash
  git clone <url>
  cd TheTechCodex
  ```
- Configurar `config.json` con tu GitHub PAT:
  ```json
  {
    "github_token": "<TU_TOKEN>",
    "settings": { /* preferencias */ }
  }
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
5. Comunicación con GitHub vía PyGithub y API REST.
6. Logging de errores en tiempo real a `logs/techcodex.log`.


## Módulo Principal: `main.py`

- **`_SCHEMA_SQL`**: SQL para crear tablas si faltan.
- **`init_db()`**: arranca BD y activa foreign keys.
- **`excepthook()`**: captura excepciones globales y las manda al logger.
- **`ProcWorker(QThread)`**: ejecuta comandos/procesos en background.
- **`MainWindow`**:
  - `_switch(self, idx)`: cambia de sección.
  - `_run_generic(self, path, hidden=False)`: ejecuta scripts/apps.
  - `_open_folder(self, path)`: abre carpetas.
  - `_log_error(self, source, message)`: graba en `techcodex.log`.


## Utilidades Comunes: `utils.py`

- **Rutas**: `BASE_DIR`, `DB_PATH`, `LOG_PATH`, `CONFIG_PATH`, etc.
- **BD**: `get_conn()`, `fetchone(sql, args)`, `fetchall()`, `exec_sql()`.
- **Files**: `get_relative_path_or_copy(src)`, manejo de assets.
- **UI**: `clear_layout()`, `RepoCard`, `AssetDialog`, `TextEditorDialog`.
- **Iconos**: `_slugify()`, `_copy_icon()`, `_pixmap()`.


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

### GitHub (`github_section.py`)
- Usa PyGithub para API.
- Vistas de repos, ramas, commits, archivos.
- Acciones: clonar, pull, commit, push, crear repo.
- Configuración de token y errores.

## Integración con GitHub

La sección `github_section.py` usa **PyGithub** y la API REST:

### Autenticación

- Se lee `github_token` de `config.json`.
- Diálogo de login con validación de token.
- Opción "Recordar sesión" guarda token cifrado si se desea.

### Repositorios

- **Listar**: carga todos los repos remotos del usuario y locales (carpeta `repos/`).
- **Clonar**:
  ```bash
  git clone https://github.com/usuario/repo.git repos/repo
  ```
- **Eliminar local**: borra carpeta `repos/<repo>`.

### Ramas

- **Listar** ramas remotas y locales.
- **Crear** rama nueva desde base:
  ```bash
  git checkout -b nueva-rama main
  ```
- En la UI, se elige rama base y nombre.

### Commits

- **Ver últimos 10**:
  - SHA corto, mensaje, fecha.
- **Pull**:
  ```bash
  git pull origin main
  ```
  - Detecta errores `safe.directory`, aplica `git config --global --add safe.directory <path>`.
- **Commit**:
  ```bash
  git add .
  git commit -m "Mensaje descriptivo"
  ```
- **Push**:
  ```bash
  git push origin nombre-rama
  ```

### Creación de Repositorios

- Formulario: nombre, visibilidad (público/privado), README inicial, licencia.
- API:
  ```python
  from github import Github
  g = Github(token)
  user = g.get_user()
  user.create_repo("nuevo-repo", private=True, auto_init=True)
  ```

### Gestión de Archivos

- **Listar** archivos locales con filtro.
- **Agregar/Eliminar**: operaciones `git add` / `os.remove()`.
- **Editar**: editor integrado para `.py`, `.md`, `.txt`, etc.
- **Abrir** con aplicación por defecto si no editable.

### Manejo de Errores

- Captura HTTP (401, 404, rate limit) y muestra mensaje claro.
- Control de permisos y `safe.directory` para evitar bloqueos.

### Google Drive Integration

Integración completa de Google Drive en la aplicación The Tech Codex. Permite autenticarse con Google, explorar archivos y carpetas del usuario (incluidos los compartidos), descargar, subir, eliminar, y acceder tanto a la versión web como a la carpeta local de descargas. Esta sección está diseñada para ser fácil de usar, completa y coherente con la interfaz de la aplicación.

---

### ✨ Características Principales

- ✉️ **Autenticación OAuth 2.0** con almacenamiento de token opcional.
- ⚙️ **Explorador de archivos** de Drive por carpetas, con soporte de navegación y botón de volver.
- 🔍 **Filtro de archivos** por nombre en tiempo real.
- 🗂️ **Visualización en tabla** con columnas: Nombre, Fecha de modificación y Tipo.
- 🔄 **Listado de archivos compartidos** usando el flag `sharedWithMe=true`.
- 📂 **Soporte de carpetas** al navegar (aunque no al descargar por ahora).
- ⬆️ **Subida de archivos** con selector de destino que distingue entre carpetas propias y compartidas.
- 🔹 **Opcion de subir directamente a la raíz** del Drive.
- 💾 **Descarga de archivos individuales o múltiples** a la carpeta local predeterminada.
- 🔍 **Soporte para abrir archivos editables** directamente en el editor integrado.
- ❌ **Eliminación segura** de archivos seleccionados.
- 🗁 **Botón Abrir Carpeta Local** para acceder a las descargas directamente.
- 🌐 **Botón Abrir Drive Web** que lanza el navegador predeterminado.

---

### 🚀 Flujo General de Uso

1. **Autenticarse** mediante el botón “Autenticación con Google”.
2. Navegar por los archivos, usar filtros y cambiar entre contenido propio y compartido.
3. Subir archivos a cualquier carpeta (propia o compartida), o directamente a la raíz.
4. Descargar uno o varios archivos. Si es editable, se puede abrir directamente en el editor.
5. Eliminar archivos que ya no necesites.
6. Abrir la carpeta local para ver los archivos descargados.
7. Acceder a la versión web de Google Drive con un clic.
8. Cerrar sesión si se desea eliminar las credenciales almacenadas.

---

### 💡 Detalles Técnicos

- Carpeta local de descargas: `storage/Google Drive`
- Límites de Google API respetados (100 elementos por página, etc.)
- Campos extraídos para cada archivo: `id`, `name`, `mimeType`, `modifiedTime`, `createdTime`
- Soporte visual y funcional para archivos `text/plain`, `markdown`, `python`, `json`, etc.
- Selector de carpeta en subida incluye etiquetas como `[Propia]` o `[Compartida]`.

---

##### 🌐 Requisitos

- Archivo `credentials.json` de Google creado desde la Google Cloud Console con acceso a Drive API.
- Token generado y almacenado en `config.json` tras autenticarse.
- Librerías necesarias:
  - `google-auth-oauthlib`
  - `google-api-python-client`
  - `PyQt6`

---

### ⚖️ Limitaciones Actuales

- No se puede descargar una carpeta completa directamente (por restricciones de la API).
- La selección de carpetas para subida no soporta navegación anidada (solo lista plana).

---

### 🔧 Módulos Relacionados

- `utils.py`: para carga/guardado de configuración y log de errores.
- `editor_section.py`: para abrir archivos editables desde Drive.

---

### 🚫 Seguridad y Privacidad

- Los tokens se almacenan localmente solo si el usuario lo permite.
- Al cerrar sesión, las credenciales se eliminan completamente.

---

### 🌟 Estado Final

Implementación **completa y funcional**, integrada perfectamente con el estilo y arquitectura de The Tech Codex.

- [x] Autenticación OAuth
- [x] Exploración completa con navegación
- [x] Subida a carpetas o raíz
- [x] Descarga masiva
- [x] Filtro en tiempo real
- [x] Visualización limpia y moderna
- [x] Acceso local y web
- [x] Eliminación y cierre de sesión

### Integración de OneDrive

---

### ✨ Características principales

- Autenticación vía OAuth2 con soporte para:
  - Renovación automática de tokens
  - Cuentas personales y de organizaciones (multi-tenant)
- Interfaz intuitiva para:
  - Visualizar archivos y carpetas
  - Navegación entre carpetas (con historial de pila)
  - Filtro rápido por nombre
  - Visualización de archivos compartidos
- Operaciones disponibles:
  - Subida de archivos a cualquier carpeta
  - Descarga directa de archivos individuales
  - Eliminación de archivos y carpetas
  - Apertura en navegador web o carpeta local
- Manejo de errores HTTP (401, 403) con intento automático de refresco
- Visualización del usuario autenticado (correo o nombre)

---

### ⚙ Configuración

Los datos de autenticación se almacenan en `config.enc` y son leídos mediante `load_config()`:

Claves requeridas:
- `client_id`
- `client_secret`
- `redirect_uri`
- `scope` (por defecto: `Files.ReadWrite.All offline_access`)
- `tenant_id` (por defecto: `common`)

Si alguna clave falta, se solicitará al usuario vía interfaz gráfica.

---

### ▶ Flujo de autenticación

1. Se genera una URL con los parámetros de OAuth2
2. Se abre el navegador predeterminado con la URL
3. El usuario inicia sesión y acepta permisos
4. La respuesta se recibe localmente en `localhost:8080`
5. Se obtiene el `code` de autorización y se intercambia por un `access_token` y `refresh_token`
6. Se almacenan y reutilizan en futuras sesiones

---

### 🌐 Scopes utilizados

```text
Files.ReadWrite.All
offline_access
User.Read (implícito para /me)
```

---

### 📁 Estructura visual en la aplicación

- **Autenticarse con OneDrive**
- **Cerrar sesión / Ver cuenta conectada**
- **Reconfigurar OneDrive** (si el usuario necesita cambiar los valores guardados)
- **Tabla de archivos** con:
  - Nombre
  - Fecha de modificación
  - Tipo (Carpeta, archivo, mimeType)
- **Botones de acción**:
  - Refrescar
  - Volver
  - Compartido conmigo
  - Subir / Descargar / Eliminar
  - Abrir carpeta local / Abrir OneDrive web

---

### ⚖ Permisos necesarios

En el portal de Microsoft Entra:
- Registrar una aplicación
- Permitir cuentas personales y organizacionales (multi-tenant)
- Establecer los scopes adecuados
- Redirigir a `http://localhost:8080`

---

### ✉ Detalles técnicos

- Cliente HTTP: `requests`
- UI: `PyQt6`
- Servidor local temporal: `wsgiref.simple_server`
- Almacenamiento: `config.enc` cifrado
- Archivos descargados: `storage/OneDrive/`

---

### ⚠ Posibles errores comunes

- `Desconocido` como nombre de cuenta: puede deberse a permisos insuficientes para leer el perfil con `/me`. Asegurarse de que `User.Read` esté habilitado implícitamente.
- Token expirado: se refresca automáticamente, pero si falla, se requerirá nueva autenticación.

---

### 🛡️ Seguridad

- Los `client_id` y `client_secret` se almacenan localmente en archivo cifrado (`config.enc`).
- Nunca se exponen los tokens en consola o UI.

---


## Base de Datos

- **SQLite** con foreign keys activadas.
- Tablas:
  - `DiariosDesarrollo`, `EntradasDesarrollo`, `Incidencias`.
  - `Consejos`, `Comandos`, `Scripts`, `Aplicaciones`.
  - `Documentacion`, `CategorySettings`, `GitHubSettings`.

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
## Configuración (`config.json`)

```json
{
  "github_token": "<PERSONAL_ACCESS_TOKEN>",
  "settings": {
    "auto_reload_news": true,
    "reload_interval_minutes": 10,
    "log_level": "INFO"
  }
}
```
- **github_token**: Token de acceso personal (PAT).
- **auto_reload_news**: Activa la recarga automática de RSS.
- **reload_interval_minutes**: Intervalo en minutos para recarga.
- **log_level**: Nivel de detalle del logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

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

- [ ] Integración con Google Drive.
- [ ] Integración con OneDrive.
- [ ] Backup y restore automático de la base de datos.
- [ ] Exportación de informes a PDF / CSV desde las distintas secciones.
