#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sections/onedrive_section.py · The Tech Codex
Integración completa con OneDrive:
- Renovación automática del token OAuth2
- Visualización del email del usuario conectado
- Manejo de errores HTTP (401, 403)
- Estructura coherente con GDriveSection
- Soporte total a través de config.enc (via load_config / save_config)
"""

import os
import time
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server, WSGIRequestHandler

import requests
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QInputDialog
)

from utils import load_config, save_config, log_execution_error

class OneDriveSection(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OneDrive Integration")
        self.resize(900, 600)

        # 1) carga segura de config
        self.full_cfg = load_config() or {}
        self.config   = self.full_cfg.get('onedrive', {})

        self.access_token     = None
        self.refresh_token    = None
        self.token_expires_at = 0
        self.current_folder_id= None
        self.folder_stack     = []

        self._build_ui()
        self._try_load_token()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Autenticación ──
        auth_row = QHBoxLayout()
        self.btn_auth    = QPushButton("🔑 Autenticarse con OneDrive")
        self.btn_logout  = QPushButton("❌ Cerrar sesión")
        self.lbl_account = QLabel("Cuenta actual: No conectado")
        auth_row.addWidget(self.btn_auth)
        auth_row.addWidget(self.btn_logout)
        auth_row.addStretch()
        auth_row.addWidget(self.lbl_account)
        layout.addLayout(auth_row)

        # ── Filtro ──
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filtro por nombre…")
        layout.addWidget(self.txt_filter)

        # ── Botones de control ──
        ctrl_row = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Refrescar")
        self.btn_back    = QPushButton("⬆ Volver")
        self.btn_shared  = QPushButton("📥 Compartido conmigo")
        ctrl_row.addWidget(self.btn_refresh)
        ctrl_row.addWidget(self.btn_back)
        ctrl_row.addWidget(self.btn_shared)
        layout.addLayout(ctrl_row)

        # ── Tabla de archivos ──
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Nombre", "Modificado", "Tipo"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # ── Acciones ──
        action_row = QHBoxLayout()
        self.btn_upload   = QPushButton("[+ Subir]")
        self.btn_download = QPushButton("⬇️ Descargar")
        self.btn_delete   = QPushButton("🗑️ Eliminar")
        action_row.addWidget(self.btn_upload)
        action_row.addWidget(self.btn_download)
        action_row.addWidget(self.btn_delete)
        layout.addLayout(action_row)

        # ── Abrir local / web ──
        access_row = QHBoxLayout()
        self.btn_open_local = QPushButton("🖥️ Abrir carpeta local")
        self.btn_open_web   = QPushButton("🌐 Abrir OneDrive Web")
        access_row.addWidget(self.btn_open_local)
        access_row.addWidget(self.btn_open_web)
        layout.addLayout(access_row)

        # ── Señales ──
        self.btn_auth.clicked.connect(self.authenticate)
        self.btn_logout.clicked.connect(self.logout)
        self.btn_refresh.clicked.connect(self.list_files)
        self.btn_back.clicked.connect(self.go_back)
        self.btn_shared.clicked.connect(self.list_shared)
        self.btn_upload.clicked.connect(self.upload_file)
        self.btn_download.clicked.connect(self.download_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_open_local.clicked.connect(self.open_local_folder)
        self.btn_open_web.clicked.connect(lambda: webbrowser.open("https://onedrive.live.com"))
        self.table.itemDoubleClicked.connect(self._handle_double)
        self.txt_filter.textChanged.connect(self._apply_filter)

    # ── OAuth2 y Tokens ──

    def authenticate(self):
        try:
            # trabajamos sobre self.config y self.full_cfg
            onedrive_cfg = self.config

            # Pedir datos si faltan
            for key in ('client_id','client_secret','redirect_uri'):
                if key not in onedrive_cfg:
                    val, ok = QInputDialog.getText(self, "Configurar OneDrive", f"Introduce {key}:")
                    if not ok or not val:
                        QMessageBox.critical(self, "Faltan datos", f"No se puede continuar sin '{key}'.")
                        return
                    onedrive_cfg[key] = val

            onedrive_cfg.setdefault('scope', 'Files.ReadWrite.All offline_access')
            onedrive_cfg.setdefault('tenant_id', 'common')

            # guardamos siempre en full_cfg
            self.full_cfg['onedrive'] = onedrive_cfg
            save_config(self.full_cfg)

            # … resto igual hasta obtener tokens …

            # Guardar tokens en el config
            onedrive_cfg.update({
                'access_token':     self.access_token,
                'refresh_token':    self.refresh_token,
                'token_expires_at': self.token_expires_at
            })
            self.full_cfg['onedrive'] = onedrive_cfg
            save_config(self.full_cfg)
            self.config = onedrive_cfg

            self.lbl_account.setText("Cuenta conectada.")
            self.list_files()
            self._show_user_email()

        except Exception as e:
            log_execution_error(str(e), "Autenticación OneDrive", "Python")
            QMessageBox.critical(self, "Error OAuth2", str(e))

    def _try_load_token(self):
        cfg = load_config().get('onedrive', {})
        self.access_token     = cfg.get('access_token')
        self.refresh_token    = cfg.get('refresh_token')
        self.token_expires_at = cfg.get('token_expires_at',0)
        if self.access_token:
            self.lbl_account.setText("Cuenta conectada.")
            self.list_files()
            self._show_user_email()

    def _refresh_access_token(self):
        if not self.refresh_token:
            return
        try:
            cfg = load_config().get('onedrive', {})
            token_url = f"https://login.microsoftonline.com/{cfg.get('tenant_id','common')}/oauth2/v2.0/token"
            resp = requests.post(token_url, data={
                'client_id':     cfg['client_id'],
                'client_secret': cfg['client_secret'],
                'grant_type':    'refresh_token',
                'refresh_token': self.refresh_token,
                'redirect_uri':  cfg['redirect_uri'],
                'scope':         cfg['scope']
            })
            data = resp.json()
            self.access_token     = data['access_token']
            self.refresh_token    = data.get('refresh_token', self.refresh_token)
            self.token_expires_at = time.time() + int(data['expires_in'])
            cfg.update({
                'access_token':     self.access_token,
                'refresh_token':    self.refresh_token,
                'token_expires_at': self.token_expires_at
            })
            full = load_config()
            full['onedrive'] = cfg
            save_config(full)
        except Exception as e:
            log_execution_error(str(e), "Refrescar token OneDrive", "Python")

    def _ensure_token(self):
        if time.time() >= self.token_expires_at - 60:
            self._refresh_access_token()

    def _authorized_request(self, method, url, **kwargs):
        self._ensure_token()
        if not self.access_token:
            raise RuntimeError("No autenticado.")
        headers = {'Authorization': f'Bearer {self.access_token}'}
        resp = requests.request(method, url, headers=headers, **kwargs)

        # Si expira o no tenemos permiso → forzar re-login
        if resp.status_code in (401, 403):
            cfg = load_config() or {}
            cfg.pop('onedrive', None)
            save_config(cfg)
            QMessageBox.warning(self, "Sesión expirada", "Tu token ha caducado o no tienes permisos. Debes volver a autenticar.")
            self.logout()
            raise RuntimeError(f"HTTP {resp.status_code}")

        return resp

    # ── Información usuario ──

    def _show_user_email(self):
        try:
            resp = self._authorized_request('GET', "https://graph.microsoft.com/v1.0/me")
            user = resp.json()
            email = user.get('mail') or user.get('userPrincipalName') or user.get('displayName','Desconocido')
            self.lbl_account.setText(f"Cuenta: {email}")
        except Exception as e:
            log_execution_error(str(e), "Obtener email OneDrive", "Python")
            self.lbl_account.setText("Cuenta: Error")

    # ── Gestión de archivos ──

    def list_files(self):
        try:
            folder = self.current_folder_id or 'root'
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder}/children"
            resp = self._authorized_request('GET', url)
            items = resp.json().get('value', [])
            self._populate_table(items)
        except Exception as e:
            log_execution_error(str(e), "Listar archivos OneDrive", "Python")
            QMessageBox.critical(self, "Error", str(e))

    def list_shared(self):
        try:
            url = "https://graph.microsoft.com/v1.0/me/drive/sharedWithMe"
            resp = self._authorized_request('GET', url)
            items = resp.json().get('value', [])
            self._populate_table(items)
        except Exception as e:
            log_execution_error(str(e), "Archivos compartidos OneDrive", "Python")
            QMessageBox.critical(self, "Error", str(e))

    def _populate_table(self, items):
        self.table.setRowCount(0)
        for itm in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name     = itm.get('name','')
            modified = itm.get('lastModifiedDateTime','—')[:19].replace('T',' ')
            is_folder= 'folder' in itm
            tipo     = "Carpeta" if is_folder else itm.get('file',{}).get('mimeType','Archivo')

            self.table.setItem(row,0, QTableWidgetItem(name))
            self.table.setItem(row,1, QTableWidgetItem(modified))
            self.table.setItem(row,2, QTableWidgetItem(tipo))
            self.table.item(row,0).setData(Qt.ItemDataRole.UserRole, itm['id'])
            self.table.item(row,2).setData(Qt.ItemDataRole.UserRole, is_folder)

    def _handle_double(self, itm):
        row = itm.row()
        is_folder = self.table.item(row,2).data(Qt.ItemDataRole.UserRole)
        fid = self.table.item(row,0).data(Qt.ItemDataRole.UserRole)
        if is_folder:
            self.folder_stack.append(self.current_folder_id)
            self.current_folder_id = fid
            self.btn_back.setEnabled(True)
            self.list_files()

    def go_back(self):
        if self.folder_stack:
            self.current_folder_id = self.folder_stack.pop()
            self.list_files()
            self.btn_back.setEnabled(bool(self.folder_stack))

    # ── Filtrado UI ──

    def _apply_filter(self, txt):
        txt = txt.lower()
        for r in range(self.table.rowCount()):
            name = self.table.item(r,0).text().lower()
            self.table.setRowHidden(r, txt not in name)

    # ── Descarga, subida y borrado ──

    def download_selected(self):
        # usamos DATA_DIR para la carpeta local
        from utils import DATA_DIR
        DOWNLOAD_DIR = Path(DATA_DIR) / "OneDrive"
        DOWNLOAD_DIR.mkdir(exist_ok=True)

        sel = self.table.selectedItems()
        if not sel: return
        row = sel[0].row()
        fid  = self.table.item(row,0).data(Qt.ItemDataRole.UserRole)
        name = self.table.item(row,0).text()
        is_folder = self.table.item(row,2).data(Qt.ItemDataRole.UserRole)
        if is_folder:
            QMessageBox.information(self, "Aviso", "No se soporta descarga de carpetas.")
            return
        try:
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{fid}/content"
            resp = self._authorized_request('GET', url)
            dest = DOWNLOAD_DIR / name
            dest.write_bytes(resp.content)
            QMessageBox.information(self, "Descarga", f"Guardado en:\n{dest}")
        except Exception as e:
            log_execution_error(str(e), "Descargar OneDrive", "Python")
            QMessageBox.critical(self, "Error", str(e))

    def upload_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona un archivo…")
        if not path: return
        name = os.path.basename(path)
        parent = self.current_folder_id or 'root'
        try:
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{parent}:/{name}:/content"
            with open(path,'rb') as f:
                resp = self._authorized_request('PUT', url, data=f)
            if resp.status_code in (200,201):
                QMessageBox.information(self, "Éxito", f"{name} subido correctamente.")
                self.list_files()
            else:
                raise RuntimeError(resp.text)
        except Exception as e:
            log_execution_error(str(e), "Subir OneDrive", "Python")
            QMessageBox.critical(self, "Error", str(e))

    def delete_selected(self):
        sel = self.table.selectedItems()
        if not sel: return
        row = sel[0].row()
        fid  = self.table.item(row,0).data(Qt.ItemDataRole.UserRole)
        name = self.table.item(row,0).text()
        if QMessageBox.question(self,"Eliminar",f"¿Borrar {name}?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) \
           != QMessageBox.StandardButton.Yes:
            return
        try:
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{fid}"
            resp = self._authorized_request('DELETE', url)
            if resp.status_code in (200,204):
                QMessageBox.information(self, "Eliminado", f"{name} eliminado.")
                self.list_files()
            else:
                raise RuntimeError(resp.text)
        except Exception as e:
            log_execution_error(str(e), "Eliminar OneDrive", "Python")
            QMessageBox.critical(self, "Error", str(e))

    # ── Abrir carpeta local ──

    def open_local_folder(self):
        try:
            folder = Path('storage/OneDrive').absolute()
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))
        except Exception as e:
            log_execution_error(str(e), "Abrir carpeta OneDrive", "Python")
            QMessageBox.critical(self, "Error", str(e))

    def logout(self):
        cfg = load_config()
        cfg.pop('onedrive', None)
        save_config(cfg)
        self.access_token = self.refresh_token = None
        self.token_expires_at = 0
        self.lbl_account.setText("No conectado")
        self.table.setRowCount(0)
        QMessageBox.information(self, "Logout", "Sesión cerrada correctamente.")