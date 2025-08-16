"""
ui/supplier_ledger.py
List purchases by supplier (simple ledger).
"""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QLabel


class SupplierLedgerDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Supplier Ledger")
        self.resize(900, 600)

        root = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Supplier name contains:"))
        self.edt_name = QLineEdit()
        row.addWidget(self.edt_name)
        btn = QPushButton("Search")
        btn.clicked.connect(self.search)
        row.addWidget(btn)
        root.addLayout(row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Purchase No", "Date/Time", "Supplier", "Items", "Total"])
        root.addWidget(self.table)

    def search(self):
        q = f"%{self.edt_name.text().strip()}%"
        rows = self.db.conn.execute(
            "SELECT p.purchase_no, p.date_time, p.supplier_name, "
            "(SELECT IFNULL(SUM(qty),0) FROM purchase_items WHERE purchase_id=p.id) AS items, "
            "p.total_amount "
            "FROM purchases p WHERE p.supplier_name LIKE ? ORDER BY p.date_time DESC",
            (q,)
        ).fetchall()
        self.table.setRowCount(0)
        for rr in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(rr["purchase_no"]))
            self.table.setItem(r, 1, QTableWidgetItem(rr["date_time"]))
            self.table.setItem(r, 2, QTableWidgetItem(rr["supplier_name"] or ""))
            self.table.setItem(r, 3, QTableWidgetItem(str(rr["items"])))
            self.table.setItem(r, 4, QTableWidgetItem(f"{float(rr['total_amount']):.2f}"))
