"""
ui/sales_analytics.py
Very basic analytics: totals & top products for date range (inclusive).
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QDateEdit, QLabel, QPushButton, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import QDate


class AnalyticsWindow(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Sales Analytics")
        self.resize(900, 600)

        root = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("From:"))
        self.dt_from = QDateEdit()
        self.dt_from.setCalendarPopup(True)
        self.dt_from.setDate(QDate.currentDate().addMonths(-1))
        row.addWidget(self.dt_from)
        row.addWidget(QLabel("To:"))
        self.dt_to = QDateEdit()
        self.dt_to.setCalendarPopup(True)
        self.dt_to.setDate(QDate.currentDate())
        row.addWidget(self.dt_to)
        btn = QPushButton("Run")
        btn.clicked.connect(self.run)
        row.addWidget(btn)
        row.addStretch()
        root.addLayout(row)

        self.tbl_summary = QTableWidget(0, 2)
        self.tbl_summary.setHorizontalHeaderLabels(["Metric", "Value"])
        root.addWidget(self.tbl_summary)

        self.tbl_top = QTableWidget(0, 3)
        self.tbl_top.setHorizontalHeaderLabels(["Barcode", "Product", "Qty Sold"])
        root.addWidget(self.tbl_top)

    def run(self):
        d1 = self.dt_from.date().toString("yyyy-MM-dd")
        d2 = self.dt_to.date().toString("yyyy-MM-dd")
        # totals
        row = self.db.conn.execute(
            "SELECT COUNT(*) AS invoices, IFNULL(SUM(total_amount),0) AS revenue "
            "FROM sales WHERE date(date_time) BETWEEN ? AND ?",
            (d1, d2)
        ).fetchone()

        self.tbl_summary.setRowCount(0)
        for k, v in [("Invoices", row["invoices"]), ("Revenue", f"{row['revenue']:.2f}")]:
            r = self.tbl_summary.rowCount()
            self.tbl_summary.insertRow(r)
            self.tbl_summary.setItem(r, 0, QTableWidgetItem(str(k)))
            self.tbl_summary.setItem(r, 1, QTableWidgetItem(str(v)))

        # top products
        rows = self.db.conn.execute(
            "SELECT barcode, description AS name, SUM(qty) AS qty "
            "FROM sale_items si JOIN sales s ON s.id = si.sale_id "
            "WHERE date(s.date_time) BETWEEN ? AND ? "
            "GROUP BY barcode, name ORDER BY qty DESC LIMIT 20",
            (d1, d2)
        ).fetchall()
        self.tbl_top.setRowCount(0)
        for rr in rows:
            r = self.tbl_top.rowCount()
            self.tbl_top.insertRow(r)
            self.tbl_top.setItem(r, 0, QTableWidgetItem(rr["barcode"] or ""))
            self.tbl_top.setItem(r, 1, QTableWidgetItem(rr["name"]))
            self.tbl_top.setItem(r, 2, QTableWidgetItem(str(rr["qty"])))
