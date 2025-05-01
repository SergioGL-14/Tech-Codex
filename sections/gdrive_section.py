import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
    QHBoxLayout, QMessageBox, QLineEdit, QFileDialog, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils import log_execution_error, load_config, save_config, DATA_DIR, BASE_DIR

# ----------------- #
# 🔧 Constantes     #
# ----------------- #
SCOPES = ['https://www.googleapis.com/auth/drive']

# helper para rutas de recursos en PyInstaller
def resource_path(rel_path: str) -> str:
    """Devuelve la ruta absoluta al recurso, compat con PyInstaller."""
    base = getattr(sys, '_MEIPASS', str(BASE_DIR))
    return os.path.join(base, rel_path)

# directorio de descargas en AppData (o ~/.local/share)
DOWNLOAD_DIR = Path(DATA_DIR) / "Google Drive"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------- #
# 🧵 Worker Thread            #
# --------------------------- #
class DriveWorker(QThread):
    update_files = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, credentials):
        super().__init__()
        self.credentials = credentials

    def run(self):
        try:
            service = build('drive', 'v3', credentials=self.credentials)
            results = service.files().list(
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, createdTime)"
            ).execute()
            items = results.get('files', [])
            self.update_files.emit(items)
        except Exception as e:
            log_execution_error(str(e), "Listar archivos Google Drive", "Python")
            self.error.emit(str(e))


# ------------------------------- #
# 🎯 Clase Principal de la Sección #
# ------------------------------- #
class GDriveSection(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Google Drive Integration")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.credentials = None
        self.service = None
        self.current_folder_id = None  # Carpeta actual (None = raíz de Drive)
        self.folder_stack = []

        self.build_ui()
        self.load_credentials()

    # ---------------- #
    # 🖥️ Interfaz      #
    # ---------------- #
    def build_ui(self):
        auth_layout = QHBoxLayout()
        self.auth_button = QPushButton("Autenticación con Google 🔑")
        self.disconnect_button = QPushButton("Desconectar cuenta ❌")
        self.account_label = QLabel("Cuenta actual: No conectado")
        self.quota_label = QLabel("Espacio usado: —")

        account_layout = QVBoxLayout()
        account_layout.setSpacing(2)
        account_layout.addWidget(self.account_label)
        account_layout.addWidget(self.quota_label)

        auth_layout.addWidget(self.auth_button)
        auth_layout.addWidget(self.disconnect_button)
        auth_layout.addLayout(account_layout)

        self.layout.addLayout(auth_layout) 

        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtro por nombre...")
        self.refresh_button = QPushButton("🔄 Refrescar Lista")
        filter_layout.addWidget(self.filter_input)
        filter_layout.addWidget(self.refresh_button)
        self.shared_button = QPushButton("📥 Compartido conmigo")
        filter_layout.addWidget(self.shared_button)
        self.layout.addLayout(filter_layout)
        self.back_button = QPushButton("⬆ Volver")
        self.back_button.setEnabled(False)
        self.back_button.clicked.connect(self.go_back)
        self.layout.addWidget(self.back_button)


        self.files_table = QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["Nombre", "Modificado", "Tipo"])
        self.files_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.files_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.layout.addWidget(self.files_table)

        access_layout = QHBoxLayout()
        self.open_local_button = QPushButton("🗂️ Abrir Carpeta Local")
        self.open_web_button = QPushButton("🌐 Abrir Google Drive Web")

        access_layout.addWidget(self.open_local_button)
        access_layout.addWidget(self.open_web_button)
        self.layout.addLayout(access_layout)

        self.open_local_button.clicked.connect(self.open_local_folder)
        self.open_web_button.clicked.connect(self.open_drive_web)

        action_layout = QHBoxLayout()
        self.upload_button = QPushButton("[+ Subir Archivo]")
        self.download_button = QPushButton("⬇️ Descargar Seleccionado")
        self.delete_button = QPushButton("🗑️ Borrar Seleccionado")

        action_layout.addWidget(self.upload_button)
        action_layout.addWidget(self.download_button)
        action_layout.addWidget(self.delete_button)

        self.download_button.clicked.connect(self.download_selected_files)
        self.layout.addLayout(action_layout)

        self.auth_button.clicked.connect(self.authenticate)
        self.disconnect_button.clicked.connect(self.disconnect)
        self.refresh_button.clicked.connect(self.list_files)
        self.upload_button.clicked.connect(self.upload_file)
        self.delete_button.clicked.connect(self.delete_selected_file)
        self.shared_button.clicked.connect(self.list_shared_files)
        self.files_table.itemDoubleClicked.connect(self.download_or_open)
        self.filter_input.textChanged.connect(self.filter_list)

    # ---------------------------------- #
    # 🔐 Autenticación Google Drive      #
    # ---------------------------------- #
    def authenticate(self):
        try:
            # ahora cargamos el cliente desde el recurso empaquetado
            creds_file = resource_path('credentials.json')
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
            self.credentials = creds
            self.service = build('drive', 'v3', credentials=self.credentials)
            self.save_credentials(creds)
            self.account_label.setText(f"Cuenta actual: {self.get_user_email()}")
            self.quota_label.setText(f"Espacio usado: {self.get_user_quota()}")
            QMessageBox.information(self, "Autenticado", "Autenticación completada con éxito.")
            self.list_files()
        except Exception as e:
            log_execution_error(str(e), "Autenticación Google Drive", "Python")
            QMessageBox.critical(self, "Error", f"Fallo en autenticación: {e}")

    def disconnect(self):
        self.credentials = None
        self.service = None
        self.account_label.setText("Cuenta actual: No conectado")
        self.clear_saved_credentials()
        QMessageBox.information(self, "Desconectado", "Cuenta desconectada correctamente.")

    def save_credentials(self, creds):
        creds_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        config = load_config() or {}
        config['google_drive'] = creds_data
        save_config(config)

    def load_credentials(self):
        config = load_config()
        if not config:
            return
        creds_data = config.get('google_drive')
        if creds_data:
            try:
                self.credentials = Credentials(
                    token=creds_data['token'],
                    refresh_token=creds_data['refresh_token'],
                    token_uri=creds_data['token_uri'],
                    client_id=creds_data['client_id'],
                    client_secret=creds_data['client_secret'],
                    scopes=creds_data['scopes']
                )
                self.service = build('drive', 'v3', credentials=self.credentials)
                self.account_label.setText(f"Cuenta actual: {self.get_user_email()}")
                self.quota_label.setText(f"Espacio usado: {self.get_user_quota()}")
                self.list_files()
            except Exception as e:
                log_execution_error(str(e), "Cargar credenciales Google Drive", "Python")

    def clear_saved_credentials(self):
        config = load_config() or {}
        config.pop('google_drive', None)
        save_config(config)

    def get_user_email(self):
        try:
            about = self.service.about().get(fields="user(emailAddress)").execute()
            return about.get('user', {}).get('emailAddress', 'Desconocido')
        except Exception as e:
            log_execution_error(str(e), "Obtener email Google Drive", "Python")
            return "Error al obtener email"
        
    def get_user_quota(self):
        try:
            about = self.service.about().get(fields="storageQuota").execute()
            quota = about.get('storageQuota', {})
            used = int(quota.get('usage', 0))
            total = int(quota.get('limit', 0))

            def to_gb(bytes_): return round(bytes_ / (1024 ** 3), 2)

            if total > 0:
                return f"{to_gb(used)} GB usados de {to_gb(total)} GB"
            else:
                return f"{to_gb(used)} GB usados (sin límite)"
        except Exception as e:
            log_execution_error(str(e), "Espacio usado Google Drive", "Python")
            return "Espacio no disponible"

    # -------------------------------- #
    # 📄 Listado de Archivos          #
    # -------------------------------- #
    def list_files(self):
        if not self.credentials:
            QMessageBox.warning(self, "Advertencia", "Debes autenticarte primero.")
            return

        try:
            q = f"'{self.current_folder_id or 'root'}' in parents and trashed=false"
            results = self.service.files().list(
                q=q,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, createdTime)"
            ).execute()
            items = results.get('files', [])
            self.populate_file_list(items)
        except Exception as e:
            log_execution_error(str(e), "Listar archivos Google Drive", "Python")
            self.show_error(str(e))

    def populate_file_list(self, items):
        self.files_table.setRowCount(0)
        for item in items:
            row = self.files_table.rowCount()
            self.files_table.insertRow(row)

            name = item.get('name', '—')
            created = item.get('createdTime')
            modified = item.get('modifiedTime')
            # Usar la fecha más relevante disponible
            date = modified or created
            formatted_date = date[:19].replace('T', ' ') if date else '—'
            mime = item.get('mimeType', '—')

            self.files_table.setItem(row, 0, QTableWidgetItem(name))
            self.files_table.setItem(row, 1, QTableWidgetItem(formatted_date))
            self.files_table.setItem(row, 2, QTableWidgetItem(mime))

            # Guardamos ID y MIME como propiedades ocultas por si se necesitan al hacer doble clic
            self.files_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get('id'))
            self.files_table.item(row, 2).setData(Qt.ItemDataRole.UserRole, mime)
            
    def filter_list(self, text):
        for row in range(self.files_table.rowCount()):
            name_item = self.files_table.item(row, 0)
            visible = text.lower() in name_item.text().lower()
            self.files_table.setRowHidden(row, not visible)

    def show_error(self, error_msg):
        QMessageBox.critical(self, "Error", error_msg)

    def list_shared_files(self):
        if not self.credentials:
            QMessageBox.warning(self, "Advertencia", "Debes autenticarte primero.")
            return

        try:
            results = self.service.files().list(
                q="sharedWithMe=true and trashed=false",
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)"
            ).execute()
            items = results.get('files', [])
            self.populate_file_list(items)
        except Exception as e:
            log_execution_error(str(e), "Listar archivos compartidos", "Python")
            self.show_error(str(e))

    # -------------------------------- #
    # 🆙 Subida de Archivos           #
    # -------------------------------- #
    def upload_file(self):
        if not self.credentials:
            QMessageBox.warning(self, "Advertencia", "Debes autenticarte primero.")
            return

        # Obtener lista de carpetas remotas
        try:
            folder_results = self.service.files().list(
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields="files(id, name, owners, shared)",
                pageSize=100
            ).execute()
            folders = folder_results.get('files', [])
        except Exception as e:
            log_execution_error(str(e), "Listar carpetas remotas", "Python")
            QMessageBox.critical(self, "Error", f"No se pudieron obtener las carpetas de Drive.\n{e}")
            return

        # Preparar lista de opciones
        folder_choices = [("📁 Raíz del Drive", None)]

        for f in folders:
            is_shared = f.get('shared', False)
            tipo = "[Compartida]" if is_shared else "[Propia]"
            label = f"{f['name']} {tipo} ({f['id']})"
            folder_choices.append((label, f['id']))

        folder_choices.sort()  # Orden alfabético

        labels = [fc[0] for fc in folder_choices]
        item, ok = QInputDialog.getItem(
            self,
            "Seleccionar carpeta",
            "Elige la carpeta destino para subir:",
            labels,
            0,
            False
        )

        if not ok:
            return  # cancelado por el usuario

        folder_id = dict(folder_choices).get(item)

        # Selección de archivo local
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo a subir")
        if file_path:
            try:
                file_name = os.path.basename(file_path)
                file_metadata = {'name': file_name}
                if folder_id:
                    file_metadata['parents'] = [folder_id]

                with open(file_path, 'rb') as media:
                    self.service.files().create(
                        body=file_metadata,
                        media_body=media
                    ).execute()

                QMessageBox.information(self, "Éxito", f"Archivo '{file_name}' subido correctamente.")
                self.list_files()
            except Exception as e:
                log_execution_error(str(e), "Subida Google Drive (con carpeta)", "Python")
                QMessageBox.critical(self, "Error", f"No se pudo subir el archivo: {e}")

    # -------------------------------- #
    # ⬇️ Descarga o Apertura         #
    # -------------------------------- #
    def download_or_open(self, item):
        row = item.row()
        name_item = self.files_table.item(row, 0)
        file_name = name_item.text()
        file_id = name_item.data(Qt.ItemDataRole.UserRole)
        mime_type = self.files_table.item(row, 2).data(Qt.ItemDataRole.UserRole)

        if mime_type == 'application/vnd.google-apps.folder':
            self.folder_stack.append(self.current_folder_id)
            self.current_folder_id = file_id
            self.back_button.setEnabled(True)
            self.list_files()
            return

        editable_types = ['text/plain', 'text/markdown', 'text/x-python', 'application/json']
        if mime_type in editable_types:
            self.download_file(file_id, file_name, open_in_editor=True)
        else:
            self.download_file(file_id, file_name)

    def download_file(self, file_id, file_name, open_in_editor=False):
        try:
            request = self.service.files().get_media(fileId=file_id)
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            file_path = os.path.join(DOWNLOAD_DIR, file_name)
            with open(file_path, 'wb') as f:
                downloader = request.execute()
                f.write(downloader)
            if open_in_editor:
                self.open_in_editor(file_path)
            else:
                os.startfile(file_path)
            QMessageBox.information(self, "Descargado", f"Archivo '{file_name}' descargado correctamente.")
        except Exception as e:
            log_execution_error(str(e), "Descarga Google Drive", "Python")
            QMessageBox.critical(self, "Error", f"No se pudo descargar el archivo: {e}")

    def open_in_editor(self, file_path):
        from editor_section import open_editor
        open_editor(file_path)

    def go_back(self):
        if self.folder_stack:
            self.current_folder_id = self.folder_stack.pop()
            self.back_button.setEnabled(bool(self.folder_stack))
            self.list_files()

    # -------------------------------- #
    # 🗑️ Borrado de Archivos         #
    # -------------------------------- #
    def delete_selected_file(self):
        selected_row = self.files_table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Sin selección", "Debes seleccionar un archivo de la tabla.")
            return

        name_item = self.files_table.item(selected_row, 0)
        file_name = name_item.text()
        file_id = name_item.data(Qt.ItemDataRole.UserRole)

        confirm = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Seguro que deseas borrar el archivo:\n\n{file_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.service.files().delete(fileId=file_id).execute()
                QMessageBox.information(self, "Borrado", f"Archivo '{file_name}' eliminado correctamente.")
                self.list_files()
            except Exception as e:
                log_execution_error(str(e), f"Borrar archivo: {file_name}", "Python")
                QMessageBox.critical(self, "Error", f"No se pudo borrar el archivo:\n{e}")

    def download_selected_files(self):
        selected_rows = self.files_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Sin selección", "Debes seleccionar al menos un archivo.")
            return

        for index in selected_rows:
            row = index.row()
            file_name = self.files_table.item(row, 0).text()
            file_id = self.files_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            mime_type = self.files_table.item(row, 2).data(Qt.ItemDataRole.UserRole)

            if mime_type == 'application/vnd.google-apps.folder':
                QMessageBox.information(self, "No implementado", f"No se puede descargar la carpeta '{file_name}' todavía.")
                continue

            # Siempre descargar sin abrir
            self.download_file(file_id, file_name, open_in_editor=False)

    def open_local_folder(self):
        try:
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            os.startfile(DOWNLOAD_DIR)
        except Exception as e:
            log_execution_error(str(e), "Abrir carpeta local", "Python")
            QMessageBox.critical(self, "Error", f"No se pudo abrir la carpeta local:\n{e}")

    def open_drive_web(self):
        import webbrowser
        try:
            webbrowser.open("https://drive.google.com/drive/my-drive")
        except Exception as e:
            log_execution_error(str(e), "Abrir Google Drive en web", "Python")
            QMessageBox.critical(self, "Error", f"No se pudo abrir Google Drive en el navegador:\n{e}")

