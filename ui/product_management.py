"""
ui/product_management.py
Product CRUD window with autocomplete suggestions on the Name/Barcode field.
Selecting a suggestion will load that product into the edit form.

Fixes:
- Avoid use of sqlite3.Row.get() (Row doesn't implement .get()).
- Use r["col"] with sensible fallbacks instead.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QDoubleSpinBox,
    QGroupBox, QGridLayout, QMessageBox, QCompleter
)
from PyQt5.QtCore import Qt, QStringListModel, QEvent
from PyQt5.QtGui import QFont


class ProductManagementWindow(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Product Management — Jadoon Shopping Mart")
        self.resize(950, 600)

        main = QVBoxLayout(self)
        header = QLabel("Product Management")
        header.setFont(QFont("Arial", 16))
        main.addWidget(header)

        # Top grid: search + form
        top_h = QHBoxLayout()
        # left: search & suggestions
        search_v = QVBoxLayout()
        search_lbl = QLabel("Search (name or barcode):")
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Type product name or barcode — suggestions appear...")
        self.input_search.returnPressed.connect(self.on_search_enter)
        search_v.addWidget(search_lbl)
        search_v.addWidget(self.input_search)

        # completer setup
        self._ac_model = QStringListModel(self)
        self._completer = QCompleter(self._ac_model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.activated[str].connect(self.on_suggestion_activated)
        self.input_search.setCompleter(self._completer)
        self.input_search.textEdited.connect(self.update_suggestions)

        top_h.addLayout(search_v, 2)

        # right: product form
        form_group = QGroupBox("Add / Edit Product")
        form = QGridLayout()
        form_group.setLayout(form)

        self.input_id = QLineEdit(); self.input_id.setReadOnly(True)
        self.input_barcode = QLineEdit()
        self.input_name = QLineEdit()
        self.input_category = QLineEdit()
        self.input_purchase = QDoubleSpinBox(); self.input_purchase.setMaximum(10_000_000); self.input_purchase.setPrefix("PKR ")
        self.input_sale = QDoubleSpinBox(); self.input_sale.setMaximum(10_000_000); self.input_sale.setPrefix("PKR ")
        self.input_stock = QSpinBox(); self.input_stock.setMaximum(10_000_000)
        self.input_tax = QDoubleSpinBox(); self.input_tax.setSuffix(" %"); self.input_tax.setMaximum(100)
        self.input_reorder = QSpinBox(); self.input_reorder.setMaximum(1000000)

        form.addWidget(QLabel("ID:"), 0, 0); form.addWidget(self.input_id, 0, 1)
        form.addWidget(QLabel("Barcode:"), 1, 0); form.addWidget(self.input_barcode, 1, 1)
        form.addWidget(QLabel("Name:"), 2, 0); form.addWidget(self.input_name, 2, 1)
        form.addWidget(QLabel("Category:"), 3, 0); form.addWidget(self.input_category, 3, 1)
        form.addWidget(QLabel("Purchase Price:"), 4, 0); form.addWidget(self.input_purchase, 4, 1)
        form.addWidget(QLabel("Sale Price:"), 5, 0); form.addWidget(self.input_sale, 5, 1)
        form.addWidget(QLabel("Stock Qty:"), 6, 0); form.addWidget(self.input_stock, 6, 1)
        form.addWidget(QLabel("Tax %:"), 7, 0); form.addWidget(self.input_tax, 7, 1)
        form.addWidget(QLabel("Reorder Level:"), 8, 0); form.addWidget(self.input_reorder, 8, 1)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Product"); self.btn_update = QPushButton("Update Product"); self.btn_delete = QPushButton("Delete Product")
        btn_row.addWidget(self.btn_add); btn_row.addWidget(self.btn_update); btn_row.addWidget(self.btn_delete)
        form.addLayout(btn_row, 9, 0, 1, 2)

        top_h.addWidget(form_group, 3)

        main.addLayout(top_h)

        # Table: product list
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["ID","Barcode","Name","Category","Purchase","Sale","Stock","Tax%","Reorder"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main.addWidget(self.table)

        # Connect buttons
        self.btn_add.clicked.connect(self.add_product)
        self.btn_update.clicked.connect(self.update_product)
        self.btn_delete.clicked.connect(self.delete_product)
        self.table.cellClicked.connect(self.on_table_click)

        # initial load
        self.refresh_products()
        self.update_suggestions("")

        # allow refresh suggestions on window activate
        self.installEventFilter(self)

    # event filter to refresh suggestions when window activates (so admin changes propagate)
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.WindowActivate:
            self.update_suggestions(self.input_search.text())
        return super().eventFilter(obj, ev)

    # suggestion helpers
    def update_suggestions(self, text):
        txt = (text or self.input_search.text() or "").strip()
        try:
            if not txt:
                rows = self.db.conn.execute("SELECT name, barcode FROM products").fetchall()
            else:
                pat = f"%{txt.lower()}%"
                rows = self.db.conn.execute(
                    "SELECT name, barcode FROM products WHERE LOWER(name) LIKE ? OR barcode LIKE ? ORDER BY name",
                    (pat, f"%{txt}%")
                ).fetchall()
        except Exception:
            rows = []

        suggestions = []
        seen = set()
        for r in rows:
            n = (r["name"] or "").strip() if r["name"] is not None else ""
            b = (r["barcode"] or "").strip() if r["barcode"] is not None else ""
            if n and n not in seen:
                suggestions.append(n); seen.add(n)
            if b and b not in seen:
                suggestions.append(b); seen.add(b)
        self._ac_model.setStringList(suggestions)

    def on_suggestion_activated(self, text):
        # when user picks a suggestion, populate the form with that product (prefer exact name/barcode)
        t = text.strip()
        if not t:
            return
        row = None
        try:
            row = self.db.conn.execute("SELECT * FROM products WHERE barcode=? LIMIT 1", (t,)).fetchone()
            if not row:
                row = self.db.conn.execute("SELECT * FROM products WHERE LOWER(name)=? LIMIT 1", (t.lower(),)).fetchone()
            if not row:
                pat = f"%{t.lower()}%"
                row = self.db.conn.execute("SELECT * FROM products WHERE LOWER(name) LIKE ? ORDER BY name LIMIT 1", (pat,)).fetchone()
        except Exception:
            row = None

        if row:
            self.load_product_row(row)

    # search enter pressed
    def on_search_enter(self):
        txt = self.input_search.text().strip()
        if not txt:
            return
        self.on_suggestion_activated(txt)

    # CRUD operations
    def refresh_products(self):
        try:
            rows = self.db.conn.execute("SELECT * FROM products ORDER BY name").fetchall()
        except Exception:
            rows = []
        self.table.setRowCount(0)
        for r in rows:
            idx = self.table.rowCount()
            self.table.insertRow(idx)
            # Use direct indexing with safe fallbacks
            pid = r["id"]
            barcode = r["barcode"] or ""
            name = r["name"] or ""
            category = r["category"] or ""
            purchase = float(r["purchase_price"] or 0.0)
            sale = float(r["sale_price"] or 0.0)
            stock = int(r["stock_qty"] or 0)
            tax = float(r["tax_percent"] or 0.0)
            reorder = int(r["reorder_level"] or 0)

            self.table.setItem(idx, 0, QTableWidgetItem(str(pid)))
            self.table.setItem(idx, 1, QTableWidgetItem(barcode))
            self.table.setItem(idx, 2, QTableWidgetItem(name))
            self.table.setItem(idx, 3, QTableWidgetItem(category))
            self.table.setItem(idx, 4, QTableWidgetItem(f"{purchase:.2f}"))
            self.table.setItem(idx, 5, QTableWidgetItem(f"{sale:.2f}"))
            self.table.setItem(idx, 6, QTableWidgetItem(str(stock)))
            self.table.setItem(idx, 7, QTableWidgetItem(f"{tax:.2f}"))
            self.table.setItem(idx, 8, QTableWidgetItem(str(reorder)))

    def clear_form(self):
        self.input_id.clear(); self.input_barcode.clear(); self.input_name.clear(); self.input_category.clear()
        self.input_purchase.setValue(0); self.input_sale.setValue(0); self.input_stock.setValue(0); self.input_tax.setValue(0); self.input_reorder.setValue(0)

    def on_table_click(self, row, col):
        try:
            self.input_id.setText(self.table.item(row, 0).text())
            self.input_barcode.setText(self.table.item(row, 1).text())
            self.input_name.setText(self.table.item(row, 2).text())
            self.input_category.setText(self.table.item(row, 3).text())
            self.input_purchase.setValue(float(self.table.item(row, 4).text()))
            self.input_sale.setValue(float(self.table.item(row, 5).text()))
            self.input_stock.setValue(int(self.table.item(row, 6).text()))
            self.input_tax.setValue(float(self.table.item(row, 7).text()))
            self.input_reorder.setValue(int(self.table.item(row, 8).text()))
        except Exception:
            pass

    def load_product_row(self, row):
        # row is a sqlite3.Row
        self.input_id.setText(str(row["id"]))
        self.input_barcode.setText(row["barcode"] or "")
        self.input_name.setText(row["name"] or "")
        self.input_category.setText(row["category"] or "")
        self.input_purchase.setValue(float(row["purchase_price"] or 0))
        self.input_sale.setValue(float(row["sale_price"] or 0))
        self.input_stock.setValue(int(row["stock_qty"] or 0))
        self.input_tax.setValue(float(row["tax_percent"] or 0))
        self.input_reorder.setValue(int(row["reorder_level"] or 0))

    def add_product(self):
        barcode = self.input_barcode.text().strip()
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Product name required."); return
        category = self.input_category.text().strip()
        purchase = float(self.input_purchase.value())
        sale = float(self.input_sale.value())
        stock = int(self.input_stock.value())
        tax = float(self.input_tax.value())
        reorder = int(self.input_reorder.value())
        if not barcode:
            # generate short numeric barcode
            import uuid
            barcode = str(uuid.uuid4().int)[:12]
        try:
            self.db.conn.execute(
                "INSERT INTO products (barcode,name,category,purchase_price,sale_price,stock_qty,tax_percent,reorder_level,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))",
                (barcode, name, category, purchase, sale, stock, tax, reorder)
            )
            self.db.conn.commit()
            QMessageBox.information(self, "Success", "Product added.")
            self.clear_form(); self.refresh_products(); self.update_suggestions("")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add product: {e}")

    def update_product(self):
        pid = self.input_id.text().strip()
        if not pid:
            QMessageBox.warning(self, "Validation", "Select product to update."); return
        barcode = self.input_barcode.text().strip()
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Product name required."); return
        category = self.input_category.text().strip()
        purchase = float(self.input_purchase.value())
        sale = float(self.input_sale.value())
        stock = int(self.input_stock.value())
        tax = float(self.input_tax.value())
        reorder = int(self.input_reorder.value())
        try:
            self.db.conn.execute(
                "UPDATE products SET barcode=?,name=?,category=?,purchase_price=?,sale_price=?,stock_qty=?,tax_percent=?,reorder_level=?,updated_at=datetime('now') WHERE id=?",
                (barcode, name, category, purchase, sale, stock, tax, reorder, int(pid))
            )
            self.db.conn.commit()
            QMessageBox.information(self, "Success", "Product updated.")
            self.clear_form(); self.refresh_products(); self.update_suggestions("")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not update product: {e}")

    def delete_product(self):
        pid = self.input_id.text().strip()
        if not pid:
            QMessageBox.warning(self, "Validation", "Select product to delete."); return
        confirm = QMessageBox.question(self, "Confirm", "Delete selected product? This cannot be undone.")
        if confirm != QMessageBox.Yes:
            return
        try:
            self.db.conn.execute("DELETE FROM products WHERE id=?", (int(pid),))
            self.db.conn.commit()
            QMessageBox.information(self, "Success", "Product deleted.")
            self.clear_form(); self.refresh_products(); self.update_suggestions("")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not delete product: {e}")
