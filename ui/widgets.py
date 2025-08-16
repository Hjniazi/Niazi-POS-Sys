"""
ui/widgets.py
Common reusable dialogs: LoginDialog, QtyDialog, ReceiptPreviewDialog
"""
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout,
    QLabel, QSpinBox, QVBoxLayout, QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt


class LoginDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Admin Login")
        self.setModal(True)
        layout = QFormLayout(self)
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        layout.addRow("Username:", self.username)
        layout.addRow("Password:", self.password)
        btn_row = QHBoxLayout()
        self.btn_login = QPushButton("Login")
        self.btn_cancel = QPushButton("Open POS Instead")
        btn_row.addWidget(self.btn_login)
        btn_row.addWidget(self.btn_cancel)
        layout.addRow(btn_row)
        self.btn_login.clicked.connect(self.try_login)
        self.btn_cancel.clicked.connect(self.reject)
        self.user = None

    def try_login(self):
        uname = self.username.text().strip()
        pwd = self.password.text()
        if not uname or not pwd:
            QMessageBox.warning(self, "Validation", "Enter both username and password.")
            return
        row = self.db.find_user(uname)
        if row is None:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")
            return
        from database.models import verify_password
        if verify_password(row["salt"], row["password_hash"], pwd):
            self.user = row
            self.accept()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")


class QtyDialog(QDialog):
    def __init__(self, current=1, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Quantity")
        layout = QFormLayout(self)
        self.spin = QSpinBox()
        self.spin.setMinimum(1)
        self.spin.setMaximum(1_000_000)
        self.spin.setValue(current)
        layout.addRow("Quantity:", self.spin)
        btn_row = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        btn_row.addWidget(self.btn_ok)
        btn_row.addWidget(self.btn_cancel)
        layout.addRow(btn_row)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def get_value(self):
        return int(self.spin.value())


class ReceiptPreviewDialog(QDialog):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 700)
        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setText(text)
        layout.addWidget(self.text)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
