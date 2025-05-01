#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
github_section.py · The Tech Codex
Integración completa con GitHub: visualizar repos, clonar, eliminar, crear ramas/repos,
gestionar archivos locales, pull, commit y push, cerrar sesión.
"""

import requests
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QListWidget,
    QLineEdit, QMessageBox, QFileDialog, QDialog, QPlainTextEdit, QInputDialog
)
from git import Repo, GitCommandError
from utils import load_config, save_config, DATA_DIR, BASE_DIR, CONFIG_PATH
from sections.github_auth_dialog import GitHubAuthDialog
from sections.github_new_repo_dialog import GitHubNewRepoDialog
import shutil
import os
import stat
import subprocess

GITHUB_API = "https://api.github.com"
# Guardamos los clones fuera del bundle, en el directorio de datos de la app:
REPOS_DIR = DATA_DIR / "repos"
REPOS_DIR.mkdir(parents=True, exist_ok=True)

EDITABLE_EXTS = [".ps1", ".py", ".txt", ".sh", ".md", ".bat", ".cmd"]

class GitHubSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._load_or_auth()
        self._build_ui()
        self._load_repos()

    def _load_or_auth(self):
        cfg = load_config() or {}
        # si no hay credenciales de GitHub en el config
        if "github" not in cfg or "username" not in cfg["github"] or "token" not in cfg["github"]:
            self._authenticate()
        else:
            gh = cfg["github"]
            self.username = gh["username"]
            self.token    = gh["token"]

    def _authenticate(self):
        dlg = GitHubAuthDialog()
        if dlg.exec() == QDialog.DialogCode.Accepted:
            username, token, remember = dlg.get_data()
            if not username or not token:
                QMessageBox.warning(self, "Datos faltantes", "Debes introducir usuario y token.")
                return
            if remember:
                cfg = load_config() or {}
                cfg['github'] = {
                    "username": username,
                    "token":    token
                }
                save_config(cfg)
            self.username = username
            self.token    = token
        else:
            QMessageBox.warning(self, "Autenticación cancelada", "No se pudo autenticar.")

    def _auth_headers(self):
        return {"Authorization": f"token {self.token}"}

    def _handle_auth_error(self):
        QMessageBox.warning(self, "⚠️ Token inválido o expirado.", "Reautentícate por favor.")
        self._authenticate()
        self._load_repos()

    def _build_ui(self):
        self.lay = QVBoxLayout(self)

        self.repo_combo = QComboBox()
        self.branch_combo = QComboBox()
        self.commit_list = QListWidget()
        self.files_list = QListWidget()

        self.commit_msg = QLineEdit()
        self.commit_msg.setPlaceholderText("Mensaje para commit...")

        btn_lay = QHBoxLayout()
        self.refresh_button = QPushButton("🔄 Refrescar")
        self.refresh_button.clicked.connect(self._load_repos)
        self.clone_button = QPushButton("📥 Clonar")
        self.clone_button.clicked.connect(self._clone_repo)
        self.delete_button = QPushButton("❌ Eliminar Local")
        self.delete_button.clicked.connect(self._delete_repo)
        self.new_repo_button = QPushButton("✨ Crear Repo")
        self.new_repo_button.clicked.connect(self._create_repo)

        btn_lay.addWidget(self.refresh_button)
        btn_lay.addWidget(self.clone_button)
        btn_lay.addWidget(self.delete_button)
        btn_lay.addWidget(self.new_repo_button)

        branch_lay = QHBoxLayout()
        self.pull_button = QPushButton("📥 Pull")
        self.pull_button.clicked.connect(self._pull_repo)
        self.new_branch_button = QPushButton("🌿 Nueva Rama")
        self.new_branch_button.clicked.connect(self._create_branch)

        branch_lay.addWidget(self.pull_button)
        branch_lay.addWidget(self.new_branch_button)

        files_top_lay = QHBoxLayout()
        files_label = QLabel("🗃️ Archivos Locales")
        self.file_search = QLineEdit()
        self.file_search.setPlaceholderText("🔍 Buscar archivo...")
        self.file_search.textChanged.connect(self._filter_files)
        self.open_folder_button = QPushButton("📂 Abrir Carpeta")
        self.open_folder_button.clicked.connect(self._open_local_folder)

        self.open_web_button = QPushButton("🌐 Abrir en GitHub Web")
        self.open_web_button.clicked.connect(self._open_in_github_web)
        files_top_lay.addWidget(self.open_web_button)

        files_top_lay.addWidget(files_label)
        files_top_lay.addWidget(self.file_search)
        files_top_lay.addWidget(self.open_folder_button)

        files_btn_lay = QHBoxLayout()
        self.add_file_button = QPushButton("➕ Añadir Archivo")
        self.add_file_button.clicked.connect(self._add_file)
        self.edit_file_button = QPushButton("📝 Ver / Editar Archivo")
        self.edit_file_button.clicked.connect(self._edit_file)
        self.delete_file_button = QPushButton("🗑️ Eliminar Archivo")
        self.delete_file_button.clicked.connect(self._delete_file)

        files_btn_lay.addWidget(self.add_file_button)
        files_btn_lay.addWidget(self.edit_file_button)
        files_btn_lay.addWidget(self.delete_file_button)

        self.commit_push_button = QPushButton("🚀 Commit & Push")
        self.commit_push_button.clicked.connect(self._push_changes)
        self.logout_button = QPushButton("🚪 Cerrar Sesión")
        self.logout_button.clicked.connect(self._logout)

        self.lay.addWidget(QLabel("📂 Repositorios"))
        self.lay.addWidget(self.repo_combo)
        self.lay.addLayout(btn_lay)
        self.lay.addWidget(QLabel("🌿 Ramas"))
        self.lay.addWidget(self.branch_combo)
        self.lay.addLayout(branch_lay)
        self.lay.addWidget(QLabel("📜 Últimos Commits"))
        self.lay.addWidget(self.commit_list)
        self.lay.addLayout(files_top_lay)
        self.lay.addWidget(self.files_list)
        self.lay.addLayout(files_btn_lay)
        self.lay.addWidget(QLabel("✏️ Mensaje de Commit"))
        self.lay.addWidget(self.commit_msg)
        self.lay.addWidget(self.commit_push_button)
        self.lay.addWidget(self.logout_button)

        self.repo_combo.currentIndexChanged.connect(self._on_repo_selected)
        self.branch_combo.currentIndexChanged.connect(self._load_commits)

    def _load_repos(self):
        if not getattr(self, "token", None):
            return
        r = requests.get(f"{GITHUB_API}/user/repos", headers=self._auth_headers())
        if r.status_code == 401:
            self._handle_auth_error()
            return
        repos = r.json()
        self.repo_combo.clear()
        self.repo_combo.addItems([repo["full_name"] for repo in repos])

    def _load_branches(self):
        repo = self.repo_combo.currentText()
        r = requests.get(f"{GITHUB_API}/repos/{repo}/branches", headers=self._auth_headers())
        if r.status_code == 401:
            self._handle_auth_error()
            return

        try:
            branches = r.json()
            self.branch_combo.clear()

            if isinstance(branches, list) and branches and isinstance(branches[0], dict) and "name" in branches[0]:
                self.branch_combo.addItems([b["name"] for b in branches])
                self._load_files()
            else:
                self.branch_combo.clear()
                QMessageBox.warning(
                    self,
                    "Repositorio vacío",
                    "Este repositorio no tiene ramas creadas todavía. ¿Añadiste README o algún archivo inicial?"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error al cargar ramas", f"Ocurrió un error al procesar las ramas:\n{e}")

    def _load_commits(self):
        repo = self.repo_combo.currentText()
        branch = self.branch_combo.currentText()
        r = requests.get(f"{GITHUB_API}/repos/{repo}/commits?sha={branch}", headers=self._auth_headers())
        if r.status_code == 401:
            self._handle_auth_error()
            return
        if r.status_code != 200:
            QMessageBox.warning(self, "Error", f"GitHub devolvió un error al obtener commits: {r.status_code}")
            return
        commits = r.json()
        if isinstance(commits, list):
            self.commit_list.clear()
            for c in commits[:10]:
                self.commit_list.addItem(f"{c['sha'][:7]}: {c['commit']['message']}")
        else:
            QMessageBox.warning(self, "Error", "GitHub devolvió un formato inesperado.")

    def _load_files(self):
        repo = self.repo_combo.currentText().replace("/", "-")
        local_path = REPOS_DIR / repo
        self.files_list.clear()
        if local_path.exists():
            for f in local_path.rglob("*"):
                # Excluir cualquier archivo o carpeta dentro de ".git"
                if ".git" not in f.parts:
                    self.files_list.addItem(str(f.relative_to(local_path)))

    def _clone_repo(self):
        repo_name = self.repo_combo.currentText()
        url = f"https://github.com/{repo_name}.git"
        local_path = REPOS_DIR / repo_name.replace("/", "-")

        if local_path.exists():
            QMessageBox.warning(self, "Ya existe", f"El repositorio local '{repo_name}' ya está clonado.")
            return

        try:
            Repo.clone_from(url, local_path)
            self._load_files()
            QMessageBox.information(self, "Clonado", f"Repositorio '{repo_name}' clonado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo clonar el repositorio:\n{e}")

    def _force_remove_readonly(self, func, path, excinfo):
        """Función auxiliar para eliminar archivos de solo lectura o bloqueados."""
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception as e:
            print(f"Error forzando la eliminación de {path}: {e}")

    def _delete_repo(self):
        repo = self.repo_combo.currentText().replace("/", "-")
        local_path = REPOS_DIR / repo
        if local_path.exists():
            confirm = QMessageBox.question(
                self, "🗑️ Confirmar eliminación",
                f"¿Seguro que quieres eliminar el repositorio local '{repo}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    shutil.rmtree(local_path, onerror=self._force_remove_readonly)
                    QMessageBox.information(self, "Eliminado", f"Repositorio '{repo}' eliminado correctamente.")
                    self._load_files()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"No se pudo eliminar el repositorio:\n{e}")

    def _pull_repo(self):
        repo = self.repo_combo.currentText().replace("/", "-")
        local_path = REPOS_DIR / repo
        try:
            Repo(local_path).remotes.origin.pull()
            self._load_commits()
        except GitCommandError as e:
            error_msg = str(e)
            if "detected dubious ownership" in error_msg:
                # Reparar automáticamente añadiendo el directorio como seguro
                try:
                    import subprocess
                    subprocess.run(
                        ["git", "config", "--global", "--add", "safe.directory", str(local_path)],
                        check=True
                    )
                    # Intentar el pull nuevamente después de marcar como seguro
                    Repo(local_path).remotes.origin.pull()
                    self._load_commits()
                    QMessageBox.information(self, "✅ Reparado", "Se añadió la ruta como segura y se realizó el pull correctamente.")
                except Exception as fix_error:
                    QMessageBox.critical(self, "Error", f"No se pudo añadir como safe.directory:\n{fix_error}")
            else:
                QMessageBox.critical(self, "Error Pull", f"No se pudo hacer pull:\n{e}")

    def _push_changes(self):
        repo = self.repo_combo.currentText().replace("/", "-")
        local_path = REPOS_DIR / repo
        commit_message = self.commit_msg.text().strip()

        if not commit_message:
            QMessageBox.warning(self, "Mensaje vacío", "Escribe un mensaje para el commit.")
            return

        try:
            repo_local = Repo(local_path)
            # Intentar git add, manejar dubious ownership automáticamente
            try:
                repo_local.git.add(all=True)
            except GitCommandError as ge:
                if "detected dubious ownership" in str(ge):
                    subprocess.run(
                        ["git", "config", "--global", "--add", "safe.directory", str(local_path)],
                        check=True
                    )
                    repo_local.git.add(all=True)
                else:
                    raise

            # Commit y push
            repo_local.index.commit(commit_message)
            repo_local.remotes.origin.push()

            self._load_commits()
            QMessageBox.information(self, "✅ Commit & Push", \
                "Commit realizado y cambios enviados correctamente al repositorio remoto.")
            self.commit_msg.clear()

        except GitCommandError as ge:
            error_msg = str(ge)
            if "detected dubious ownership" in error_msg:
                QMessageBox.critical(self, "Error", \
                    "Error de ownership aún persiste tras marcar safe.directory.")
            else:
                QMessageBox.critical(self, "Error Commit", f"No se pudo hacer commit o push:\n{error_msg}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo hacer commit y push:\n{e}")

    def _logout(self):
        cfg = load_config() or {}
        cfg.pop('github', None)
        save_config(cfg)
        QMessageBox.information(self, "Logout", "Sesión cerrada correctamente.")
        self._load_or_auth()
        self._load_repos()

    def _create_branch(self):
        repo = self.repo_combo.currentText()
        new_branch, ok = QInputDialog.getText(self, "🌿 Crear nueva rama", "Nombre de la rama:")
        if ok and new_branch:
            branch_from = self.branch_combo.currentText()
            url = f"{GITHUB_API}/repos/{repo}/git/refs"
            r = requests.get(f"{url}/heads/{branch_from}", headers=self._auth_headers())
            if r.status_code == 200:
                sha = r.json()["object"]["sha"]
                data = {"ref": f"refs/heads/{new_branch}", "sha": sha}
                r = requests.post(url, json=data, headers=self._auth_headers())
                if r.status_code == 201:
                    QMessageBox.information(self, "🌿 Rama creada", f"Rama '{new_branch}' creada correctamente.")
                    self._load_branches()
                else:
                    QMessageBox.critical(self, "Error", f"No se pudo crear la rama:\n{r.json()}")
            else:
                QMessageBox.critical(self, "Error", "Error obteniendo información de rama actual.")

    def _create_repo(self):
        dlg = GitHubNewRepoDialog()
        if dlg.exec() == QDialog.DialogCode.Accepted:
            repo_name, include_readme, license_template, is_private = dlg.get_data()

            if not repo_name:
                QMessageBox.warning(self, "Datos faltantes", "Debes introducir el nombre del repositorio.")
                return

            url = f"{GITHUB_API}/user/repos"
            data = {
                "name": repo_name,
                "private": is_private,
                "auto_init": include_readme
            }

            if license_template:
                data["license_template"] = license_template

            try:
                r = requests.post(url, json=data, headers=self._auth_headers())
                if r.status_code == 201:
                    QMessageBox.information(self, "✨ Repo creado", f"Repositorio '{repo_name}' creado correctamente.")
                    local_path = REPOS_DIR / repo_name
                    local_path.mkdir(parents=True, exist_ok=True)
                    Repo.init(local_path)
                    self._load_repos()
                else:
                    error_message = r.json().get("message", "Error desconocido.")
                    QMessageBox.critical(self, "Error", f"No se pudo crear el repo:\n{error_message}")
            except Exception as e:
                QMessageBox.critical(self, "Error inesperado", f"Ocurrió un error al crear el repositorio:\n{e}")

    def _add_file(self):
        repo = self.repo_combo.currentText().replace("/", "-")
        local_path = REPOS_DIR / repo
        file_path, _ = QFileDialog.getOpenFileName(self, "➕ Seleccionar archivo a añadir")
        if file_path:
            shutil.copy(file_path, local_path)
            QMessageBox.information(self, "Archivo añadido", "Archivo copiado correctamente.")
            self._load_files()

    def _edit_file(self):
        repo = self.repo_combo.currentText().replace("/", "-")
        local_path = REPOS_DIR / repo
        selected_item = self.files_list.currentItem()

        if selected_item:
            file_path = local_path / selected_item.text()
            ext = file_path.suffix.lower()

            if ext in EDITABLE_EXTS:
                # Editar archivos de texto
                content = None
                encodings_to_try = ['utf-8', 'latin1', 'cp1252', 'utf-16']
                for enc in encodings_to_try:
                    try:
                        content = file_path.read_text(encoding=enc)
                        break
                    except UnicodeDecodeError:
                        continue

                if content is None:
                    QMessageBox.critical(self, "Error", "No se pudo decodificar el archivo con las codificaciones probadas.")
                    return

                editor = QDialog(self)
                editor.setWindowTitle(f"📝 Editando: {file_path.name}")
                editor.resize(600, 500)
                lay = QVBoxLayout(editor)
                txt_edit = QPlainTextEdit(content, editor)
                save_btn = QPushButton("💾 Guardar Cambios", editor)
                lay.addWidget(txt_edit)
                lay.addWidget(save_btn)

                def save_changes():
                    try:
                        file_path.write_text(txt_edit.toPlainText(), encoding='utf-8')
                        QMessageBox.information(editor, "Guardado", "Archivo guardado correctamente.")
                        editor.accept()
                    except Exception as e:
                        QMessageBox.critical(editor, "Error", f"No se pudo guardar:\n{e}")

                save_btn.clicked.connect(save_changes)
                editor.exec()

            else:
                # Ver archivos no editables (PDFs, imágenes, etc.)
                try:
                    os.startfile(file_path)  # Abre con la app predeterminada de Windows
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"No se pudo abrir el archivo:\n{e}")
        else:
            QMessageBox.warning(self, "Sin selección", "Debes seleccionar un archivo primero.")

    def _delete_file(self):
        repo = self.repo_combo.currentText().replace("/", "-")
        local_path = REPOS_DIR / repo
        selected_item = self.files_list.currentItem()
        if selected_item:
            file_path = local_path / selected_item.text()
            if file_path.exists():
                confirm = QMessageBox.question(self, "🗑️ Confirmar eliminación", f"¿Seguro que quieres eliminar '{selected_item.text()}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if confirm == QMessageBox.StandardButton.Yes:
                    file_path.unlink()
                    QMessageBox.information(self, "Eliminado", "Archivo eliminado correctamente.")
                    self._load_files()
            else:
                QMessageBox.warning(self, "Error", "El archivo seleccionado no existe.")
            
    def _filter_files(self):
        filter_text = self.file_search.text().lower()
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            item.setHidden(filter_text not in item.text().lower())

    def _open_local_folder(self):
        repo = self.repo_combo.currentText().replace("/", "-")
        local_path = REPOS_DIR / repo
        if local_path.exists():
            import os
            os.startfile(local_path)  # Windows específico
        else:
            QMessageBox.warning(self, "Carpeta no encontrada", "El repositorio local no existe.")

    def _on_repo_selected(self):
        repo = self.repo_combo.currentText()
        if repo:
            self._load_branches()  # Solo carga ramas si hay repo seleccionado

    def _open_in_github_web(self):
        import webbrowser
        repo = self.repo_combo.currentText()
        if not repo:
            QMessageBox.warning(self, "Sin repositorio", "No hay repositorio seleccionado.")
            return
        url = f"https://github.com/{repo}"
        try:
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el navegador:\n{e}")

