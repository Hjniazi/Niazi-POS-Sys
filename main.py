#!/usr/bin/env python3
"""
main.py — Entry point for JadoonPOS
"""
import sys
from PyQt5.QtWidgets import QApplication
from config.style import load_app_style
from database.db import DB
from ui.admin_window import AdminWindow
from ui.pos_window import POSWindow
from ui.widgets import LoginDialog


DB_FILE = "store.db"


def main():
    app = QApplication(sys.argv)

    # stylesheet
    qss = load_app_style()
    if qss:
        app.setStyleSheet(qss)

    # database
    db = DB(DB_FILE)

    # Try admin login; if cancelled or non-admin, go to POS
    login = LoginDialog(db)
    if login.exec_() == login.Accepted and login.user and login.user["role"] == "admin":
        win = AdminWindow(db)
    else:
        win = POSWindow(db)

    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
