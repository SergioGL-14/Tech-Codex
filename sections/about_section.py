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

        # Create QTextBrowser
        browser = QTextBrowser()
        # Load the markdown via resource_path, pointing at the bundle or the dev tree
        md_file = resource_path("ABOUT.md")
        md = Path(md_file).read_text(encoding="utf-8")
        browser.setMarkdown(md)

        # 1) Do not open links internally by default
        browser.setOpenLinks(False)
        # 2) But do open automatic http(s) links externally
        browser.setOpenExternalLinks(True)
        # 3) Hook clicks on internal anchors
        browser.anchorClicked.connect(self._on_anchor)

        lay.addWidget(browser)
        self._browser = browser

    def _on_anchor(self, url: QUrl) -> None:
        # A link with fragment "#something" makes QUrl.toString() return "#something"
        frag = url.toString()
        # Scroll to that anchor
        # QTextBrowser expects it without the "#"
        if frag.startswith('#'):
            self._browser.scrollToAnchor(frag[1:])
        else:
            # for external links (http://...) let the system open them
            import webbrowser
            webbrowser.open(frag)