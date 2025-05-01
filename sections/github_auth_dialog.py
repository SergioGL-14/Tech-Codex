from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox

class GitHubAuthDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Autenticación GitHub")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Username de GitHub:"))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)

        layout.addWidget(QLabel("Personal Access Token (PAT):"))
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.token_input)

        self.remember_checkbox = QCheckBox("Recordar estos datos")
        layout.addWidget(self.remember_checkbox)

        self.ok_button = QPushButton("Aceptar")
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

    def get_data(self):
        return (
            self.username_input.text(),
            self.token_input.text(),
            self.remember_checkbox.isChecked()
        )