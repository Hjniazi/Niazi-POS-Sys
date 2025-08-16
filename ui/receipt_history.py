"""
ui/receipt_history.py

Dialog to view receipt (sales) history and open saved receipt PDF/TXT files.
"""

import os
import sys
import subprocess
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

RECEIPT_DIR = "receipts"


def open_file_with_default_app(path):
    """Cross-platform method to open a file with the default application."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.call(["open", path])
    else:
        # Assume Linux / xdg-open
        subprocess.call(["xdg-open", path])


class ReceiptHistoryDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Receipt History")
        self.resize(800, 500)

        layout = QVBoxLayout(self)

        header = QLabel("Receipt History")
        header.setFont(QFont("Arial", 14, QFont.Bold))
        header.setAlignment(Qt.AlignLeft)
        layout.addWidget(header)

        # Search bar
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search invoice no (type and press Enter or use live filter)...")
        self.search_input.textChanged.connect(self.filter_table)
        search_row.addWidget(self.search_input)

        self.btn_open = QPushButton("Open Selected")
        self.btn_open.clicked.connect(self.open_selected)
        search_row.addWidget(self.btn_open)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.load_sales)
        search_row.addWidget(self.btn_refresh)

        layout.addLayout(search_row)

        # Table: Invoice No | Date | Total | Receipt Exists
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Invoice No", "Date / Time", "Total", "Receipt File"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)
        self.table.cellDoubleClicked.connect(self.on_double_click)
        layout.addWidget(self.table)

        # Load data
        self.all_rows = []  # cached rows from DB
        self.load_sales()

    def load_sales(self):
        """Load sales from DB and populate the table (most recent first)."""
        try:
            c = self.db.conn.cursor()
            c.execute("SELECT id, invoice_no, date_time, total_amount FROM sales ORDER BY date_time DESC")
            rows = c.fetchall()
        except Exception:
            rows = []

        self.all_rows = []
        for r in rows:
            invoice_no = r["invoice_no"] or ""
            dt = r["date_time"] or ""
            total = r["total_amount"] or 0.0
            # detect file path (pdf preferred)
            pdf_path = os.path.join(RECEIPT_DIR, f"{invoice_no}.pdf")
            txt_path = os.path.join(RECEIPT_DIR, f"{invoice_no}.txt")
            exists = None
            if os.path.isfile(pdf_path):
                exists = pdf_path
            elif os.path.isfile(txt_path):
                exists = txt_path
            else:
                exists = None
            self.all_rows.append({
                "id": r["id"],
                "invoice_no": invoice_no,
                "date_time": dt,
                "total": total,
                "file": exists
            })

        # populate table
        self.filter_table()

    def filter_table(self, _text=None):
        """Filter table using search input (substring match on invoice_no)."""
        q = (self.search_input.text() or "").strip().lower()
        self.table.setRowCount(0)
        for r in self.all_rows:
            if q and q not in (r["invoice_no"] or "").lower():
                continue
            idx = self.table.rowCount()
            self.table.insertRow(idx)
            self.table.setItem(idx, 0, QTableWidgetItem(r["invoice_no"]))
            # format date/time nicely if possible
            dt_str = r["date_time"] or ""
            try:
                # try parsing ISO
                dt = datetime.fromisoformat(dt_str) if dt_str else None
                dt_display = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""
            except Exception:
                dt_display = dt_str
            self.table.setItem(idx, 1, QTableWidgetItem(dt_display))
            self.table.setItem(idx, 2, QTableWidgetItem(f"{(r['total'] or 0.0):.2f}"))
            self.table.setItem(idx, 3, QTableWidgetItem(os.path.basename(r["file"]) if r["file"] else "MISSING"))
            # attach full data to first cell for retrieval
            self.table.item(idx, 0).setData(Qt.UserRole, r)

    def get_selected_row_data(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return data

    def open_selected(self):
        data = self.get_selected_row_data()
        if not data:
            QMessageBox.information(self, "Select", "Please select a receipt row to open.")
            return
        file_path = data.get("file")
        invoice_no = data.get("invoice_no")
        if not file_path or not os.path.isfile(file_path):
            QMessageBox.warning(self, "Missing", f"No receipt file found for invoice {invoice_no}.")
            return
        try:
            open_file_with_default_app(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Open Failed", f"Could not open file: {e}")

    def on_double_click(self, row, col):
        # open double-clicked row
        self.open_selected()
