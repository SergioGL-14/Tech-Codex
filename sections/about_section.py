# sections/about_section.py
# -*- coding: utf-8 -*-

from pathlib import Path
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser
from utils import resource_path

class AboutSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)

        # Crear QTextBrowser
        browser = QTextBrowser()
        # Cargar el markdown usando resource_path para apuntar al bundle o al desarrollo
        md_file = resource_path("ABOUT.md")
        md = Path(md_file).read_text(encoding="utf-8")
        browser.setMarkdown(md)

        # 1) No abrir internamente los links por defecto
        browser.setOpenLinks(False)
        # 2) Pero sí abrir externamente los http(s) automáticos
        browser.setOpenExternalLinks(True)
        # 3) Conectar el clic en anclas internas
        browser.anchorClicked.connect(self._on_anchor)

        lay.addWidget(browser)
        self._browser = browser

    def _on_anchor(self, url: QUrl) -> None:
        # Si es un link con fragmento "#algo", QUrl.toString() será "#algo"
        frag = url.toString()
        # Mover el scroll a esa ancla
        # QTextBrowser espera sin el “#”
        if frag.startswith('#'):
            self._browser.scrollToAnchor(frag[1:])
        else:
            # para enlaces externos (http://...) dejamos que el sistema los abra
            import webbrowser
            webbrowser.open(frag)