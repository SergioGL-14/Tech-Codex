from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QFileDialog,
    QColorDialog, QFontDialog, QMessageBox
)
from PyQt6.QtGui import QTextCharFormat, QTextCursor, QColor, QFont
from PyQt6.QtCore import Qt
import os


class EditorSection(QWidget):
    def __init__(self, file_path=None):
        super().__init__()
        self.setWindowTitle("Editor de Documentos 📝")
        self.resize(800, 600)

        self.file_path = file_path
        self.init_ui()

        if file_path:
            self.load_file(file_path)

    # -------------------- #
    # 🧱 Interfaz Principal #
    # -------------------- #
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Editor
        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)

        # Barra de herramientas
        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)

        btn_bold = QPushButton("Negrita")
        btn_bold.clicked.connect(self.make_bold)
        toolbar.addWidget(btn_bold)

        btn_italic = QPushButton("Cursiva")
        btn_italic.clicked.connect(self.make_italic)
        toolbar.addWidget(btn_italic)

        btn_underline = QPushButton("Subrayado")
        btn_underline.clicked.connect(self.make_underline)
        toolbar.addWidget(btn_underline)

        btn_color = QPushButton("Color")
        btn_color.clicked.connect(self.change_color)
        toolbar.addWidget(btn_color)

        btn_font = QPushButton("Fuente")
        btn_font.clicked.connect(self.change_font)
        toolbar.addWidget(btn_font)

        btn_open = QPushButton("📂 Abrir")
        btn_open.clicked.connect(self.open_file_dialog)
        toolbar.addWidget(btn_open)

        btn_save = QPushButton("💾 Guardar")
        btn_save.clicked.connect(self.save_file)
        toolbar.addWidget(btn_save)

    # -------------------- #
    # 🎨 Formateo de Texto #
    # -------------------- #
    def apply_format(self, fmt: QTextCharFormat):
        cursor = self.text_edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(fmt)

    def make_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold)
        self.apply_format(fmt)

    def make_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(True)
        self.apply_format(fmt)

    def make_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(True)
        self.apply_format(fmt)

    def change_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self.apply_format(fmt)

    def change_font(self):
        font, ok = QFontDialog.getFont()
        if ok:
            fmt = QTextCharFormat()
            fmt.setFont(font)
            self.apply_format(fmt)

    # ---------------- #
    # 📂 Abrir Archivo #
    # ---------------- #
    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir archivo")
        if file_path:
            self.file_path = file_path
            self.load_file(file_path)

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_edit.setPlainText(content)
            self.setWindowTitle(f"Editor - {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el archivo:\n{e}")

    # ----------------- #
    # 💾 Guardar Archivo #
    # ----------------- #
    def save_file(self):
        if not self.file_path:
            self.file_path, _ = QFileDialog.getSaveFileName(self, "Guardar como")
            if not self.file_path:
                return
        try:
            content = self.text_edit.toPlainText()
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            QMessageBox.information(self, "Guardado", "Archivo guardado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo:\n{e}")


# ---------------------------- #
# 🌐 Función accesible externa #
# ---------------------------- #
def open_editor(file_path):
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    editor = EditorSection(file_path)
    editor.show()

    if not QApplication.instance():
        app.exec()