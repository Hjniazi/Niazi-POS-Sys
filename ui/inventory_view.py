"""
ui/inventory_view.py
Inventory list with low-stock highlight.
"""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem
from PyQt5.QtGui import QColor
from config.settings import AppSettings


class InventoryDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Inventory")
        self.resize(900, 600)
        self.settings = AppSettings(db)
        root = QVBoxLayout(self)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["ID", "Barcode", "Name", "Category", "Stock", "Reorder", "Sale Price"])
        self.table.setColumnHidden(0, True)
        root.addWidget(self.table)

        self.refresh()

    def refresh(self):
        low_thr = self.settings.low_stock_threshold
        rows = self.db.conn.execute("SELECT * FROM products ORDER BY name").fetchall()
        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(row["id"])))
            self.table.setItem(r, 1, QTableWidgetItem(row["barcode"] or ""))
            self.table.setItem(r, 2, QTableWidgetItem(row["name"]))
            self.table.setItem(r, 3, QTableWidgetItem(row["category"] or ""))
            self.table.setItem(r, 4, QTableWidgetItem(str(row["stock_qty"])))
            self.table.setItem(r, 5, QTableWidgetItem(str(row["reorder_level"])))
            self.table.setItem(r, 6, QTableWidgetItem(f"{row['sale_price']:.2f}"))
            if int(row["stock_qty"]) <= max(low_thr, int(row["reorder_level"] or 0)):
                for c in range(self.table.columnCount()):
                    self.table.item(r, c).setBackground(QColor("#fff0f0"))
