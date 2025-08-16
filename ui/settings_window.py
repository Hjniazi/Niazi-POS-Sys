"""
ui/settings_window.py
Settings editor dialog (store name, default tax, receipt footer, low stock threshold, admin password)
"""

from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QSpinBox, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class SettingsWindow(QDialog):
    def __init__(self, db, parent=None):
        """
        Accepts parent optionally (fixed crash where caller used parent=...).
        """
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Settings — Jadoon Shopping Mart")
        self.resize(600, 420)

        main = QVBoxLayout(self)
        header = QLabel("Store Settings")
        header.setFont(QFont("Arial", 14))
        main.addWidget(header)

        form = QFormLayout()
        self.input_store_name = QLineEdit()
        self.input_tax = QLineEdit()
        self.input_footer = QLineEdit()
        self.input_low_stock = QSpinBox()
        self.input_low_stock.setMinimum(0)
        self.input_low_stock.setMaximum(1000000)

        # load from db (settings table helper in database/db.py)
        self.input_store_name.setText(self.db.get_setting("store_name", "JADOON SHOPPING MART"))
        self.input_tax.setText(self.db.get_setting("default_tax_percent", "0"))
        self.input_footer.setText(self.db.get_setting("receipt_footer", "Thank you for shopping with Jadoon Shopping Mart!"))
        try:
            self.input_low_stock.setValue(int(self.db.get_setting("low_stock_threshold", "5")))
        except Exception:
            self.input_low_stock.setValue(5)

        form.addRow("Store Name:", self.input_store_name)
        form.addRow("Default Tax %:", self.input_tax)
        form.addRow("Receipt Footer:", self.input_footer)
        form.addRow("Low-stock Threshold:", self.input_low_stock)

        grp = QGroupBox("Security")
        grp_layout = QFormLayout(grp)
        self.input_admin_user = QLineEdit()
        self.input_admin_user.setText("admin")
        self.input_admin_user.setReadOnly(True)
        self.input_admin_pw = QLineEdit()
        self.input_admin_pw.setEchoMode(QLineEdit.Password)
        grp_layout.addRow("Admin user (fixed):", self.input_admin_user)
        grp_layout.addRow("Set new admin password (leave blank to keep):", self.input_admin_pw)

        main.addLayout(form)
        main.addWidget(grp)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_cancel = QPushButton("Cancel")
        btn_row.addStretch()
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_cancel)
        main.addLayout(btn_row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self.save_settings)

    def save_settings(self):
        store_name = self.input_store_name.text().strip()
        tax = self.input_tax.text().strip()
        footer = self.input_footer.text().strip()
        low_stock = int(self.input_low_stock.value())

        if not store_name:
            QMessageBox.warning(self, "Validation", "Store name cannot be empty.")
            return
        # save settings
        try:
            self.db.set_setting("store_name", store_name)
            self.db.set_setting("default_tax_percent", tax)
            self.db.set_setting("receipt_footer", footer)
            self.db.set_setting("low_stock_threshold", str(low_stock))
            # update password if provided
            new_pw = self.input_admin_pw.text()
            if new_pw:
                self.db.update_user_password("admin", new_pw)
            QMessageBox.information(self, "Saved", "Settings saved successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save settings: {e}")
