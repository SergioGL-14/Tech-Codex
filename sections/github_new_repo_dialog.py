from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QComboBox
)

class GitHubNewRepoDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("✨ Crear Repositorio")
        self.resize(350, 220)

        layout = QVBoxLayout(self)

        # Nombre del repositorio
        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Nombre del nuevo repo...")
        layout.addWidget(QLabel("📂 Nombre del repositorio:"))
        layout.addWidget(self.name_input)

        # Incluir README
        self.readme_checkbox = QCheckBox("📄 Incluir README.md", self)
        layout.addWidget(self.readme_checkbox)

        # Licencia
        layout.addWidget(QLabel("📜 Licencia:"))
        self.license_combo = QComboBox(self)
        self.license_combo.addItem("Sin licencia", "")
        self.license_combo.addItem("MIT", "mit")
        self.license_combo.addItem("GPL v3", "gpl-3.0")
        self.license_combo.addItem("Apache 2.0", "apache-2.0")
        self.license_combo.addItem("BSD 2-Clause", "bsd-2-clause")
        self.license_combo.addItem("BSD 3-Clause", "bsd-3-clause")
        self.license_combo.addItem("Unlicense", "unlicense")
        self.license_combo.addItem("MPL 2.0", "mpl-2.0")
        layout.addWidget(self.license_combo)

        # Público o Privado
        self.private_checkbox = QCheckBox("🔒 Privado", self)
        layout.addWidget(self.private_checkbox)

        # Botones OK / Cancel
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # Conexión de botones
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_data(self):
        return (
            self.name_input.text().strip(),
            self.readme_checkbox.isChecked(),
            self.license_combo.currentData(),
            self.private_checkbox.isChecked()
        )