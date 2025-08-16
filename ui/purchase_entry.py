"""
ui/purchase_entry.py
Purchase entry dialog with autocomplete suggestions on the product search field.
Select or type product name/barcode (suggestions appear), set qty & unit price, add to purchase.
Saving the purchase will create purchase and purchase_items and update stock.
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QDoubleSpinBox,
    QMessageBox, QFormLayout, QGroupBox, QInputDialog, QCompleter
)
from PyQt5.QtCore import Qt, QStringListModel, QEvent
from PyQt5.QtGui import QFont
import uuid
from datetime import datetime

class PurchaseEntryDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Purchase Entry — Jadoon Shopping Mart")
        self.resize(900, 600)

        v = QVBoxLayout(self)
        header = QLabel("Purchase Entry")
        header.setFont(QFont("Arial", 14))
        v.addWidget(header)

        # supplier selection
        supplier_h = QHBoxLayout()
        supplier_h.addWidget(QLabel("Supplier:"))
        self.cmb_supplier = QComboBox()
        self.btn_add_supplier = QPushButton("Add Supplier")
        supplier_h.addWidget(self.cmb_supplier)
        supplier_h.addWidget(self.btn_add_supplier)
        v.addLayout(supplier_h)
        self.btn_add_supplier.clicked.connect(self.add_supplier)

        # product search + item add area
        top_h = QHBoxLayout()
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Type product name or barcode — suggestions will appear...")
        self.input_search.returnPressed.connect(self.on_search_enter)
        top_h.addWidget(QLabel("Product:"))
        top_h.addWidget(self.input_search)

        # completer
        self._ac_model = QStringListModel(self)
        self._completer = QCompleter(self._ac_model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.activated[str].connect(self.on_suggestion_activated)
        self.input_search.setCompleter(self._completer)
        self.input_search.textEdited.connect(self.update_suggestions)

        # qty/price
        self.spin_qty = QSpinBox(); self.spin_qty.setMinimum(1); self.spin_qty.setMaximum(1_000_000)
        self.spin_price = QDoubleSpinBox(); self.spin_price.setMaximum(10_000_000); self.spin_price.setPrefix("PKR ")
        top_h.addWidget(QLabel("Qty:")); top_h.addWidget(self.spin_qty)
        top_h.addWidget(QLabel("Unit Price:")); top_h.addWidget(self.spin_price)
        self.btn_add_item = QPushButton("Add Item")
        top_h.addWidget(self.btn_add_item)
        v.addLayout(top_h)
        self.btn_add_item.clicked.connect(self.add_item_to_table)

        # items table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Barcode","Description","Qty","Unit Price","Line Total","ProductID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnHidden(5, True)
        v.addWidget(self.table)

        # totals and actions
        bottom_h = QHBoxLayout()
        self.lbl_total = QLabel("Total: PKR 0.00")
        bottom_h.addWidget(self.lbl_total)
        bottom_h.addStretch()
        self.btn_save = QPushButton("Save Purchase")
        self.btn_cancel = QPushButton("Cancel")
        bottom_h.addWidget(self.btn_save); bottom_h.addWidget(self.btn_cancel)
        v.addLayout(bottom_h)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self.save_purchase)

        # load suppliers & suggestions
        self.load_suppliers()
        self.update_suggestions("")
        self.installEventFilter(self)
        self._selected_product = None

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.WindowActivate:
            self.load_suppliers()
            self.update_suggestions(self.input_search.text())
        return super().eventFilter(obj, ev)

    def load_suppliers(self):
        self.cmb_supplier.clear()
        try:
            rows = self.db.conn.execute("SELECT id,name FROM suppliers ORDER BY name").fetchall()
        except Exception:
            rows = []
        for r in rows:
            self.cmb_supplier.addItem(r["name"], r["id"])

    def add_supplier(self):
        # prompt for supplier details
        name, ok = QInputDialog.getText(self, "Add Supplier", "Supplier name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        contact, ok2 = QInputDialog.getText(self, "Add Supplier", "Contact info (optional):")
        if not ok2:
            contact = ""
        notes, ok3 = QInputDialog.getText(self, "Add Supplier", "Notes (optional):")
        if not ok3:
            notes = ""
        try:
            self.db.conn.execute(
                "INSERT INTO suppliers (name, contact, notes, created_at) VALUES (?, ?, ?, ?)",
                (name, contact or "", notes or "", datetime.utcnow().isoformat())
            )
            self.db.conn.commit()
            QMessageBox.information(self, "Added", "Supplier added.")
            self.load_suppliers()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add supplier: {e}")

    def update_suggestions(self, text):
        txt = (text or "").strip()
        try:
            if not txt:
                rows = self.db.conn.execute("SELECT name,barcode FROM products").fetchall()
            else:
                pat = f"%{txt.lower()}%"
                rows = self.db.conn.execute(
                    "SELECT name,barcode FROM products WHERE LOWER(name) LIKE ? OR barcode LIKE ? ORDER BY name",
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
        self.input_search.setText(text)
        # optionally auto-fill unit price if product exists
        try:
            row = self.db.conn.execute(
                "SELECT * FROM products WHERE barcode=? OR LOWER(name)=? LIMIT 1", (text, text.lower())
            ).fetchone()
        except Exception:
            row = None
        if row:
            self.spin_price.setValue(float(row["purchase_price"] or 0))
            self._selected_product = row
        else:
            self._selected_product = None

    def on_search_enter(self):
        self.on_suggestion_activated(self.input_search.text().strip())

    def add_item_to_table(self):
        text = self.input_search.text().strip()
        if not text:
            QMessageBox.warning(self, "Validation", "Select a product or type its name/barcode."); return
        # find product (prefer exact barcode then exact name then partial)
        try:
            row = self.db.conn.execute("SELECT * FROM products WHERE barcode=? LIMIT 1", (text,)).fetchone()
            if not row:
                row = self.db.conn.execute("SELECT * FROM products WHERE LOWER(name)=? LIMIT 1", (text.lower(),)).fetchone()
            if not row:
                pat = f"%{text.lower()}%"
                row = self.db.conn.execute("SELECT * FROM products WHERE LOWER(name) LIKE ? ORDER BY name LIMIT 1", (pat,)).fetchone()
        except Exception:
            row = None

        barcode = row["barcode"] if row else ""
        desc = (row["name"] if row else text)
        prod_id = int(row["id"]) if row else None
        qty = int(self.spin_qty.value())
        unit_price = float(self.spin_price.value())
        line_total = qty * unit_price

        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(barcode))
        self.table.setItem(r, 1, QTableWidgetItem(desc))
        self.table.setItem(r, 2, QTableWidgetItem(str(qty)))
        self.table.setItem(r, 3, QTableWidgetItem(f"{unit_price:.2f}"))
        self.table.setItem(r, 4, QTableWidgetItem(f"{line_total:.2f}"))
        self.table.setItem(r, 5, QTableWidgetItem(str(prod_id) if prod_id else ""))

        # reset inputs
        self.input_search.clear(); self.spin_qty.setValue(1); self.spin_price.setValue(0.0)
        self._selected_product = None
        self.recompute_total()

    def recompute_total(self):
        total = 0.0
        for r in range(self.table.rowCount()):
            try:
                total += float(self.table.item(r, 4).text())
            except Exception:
                pass
        self.lbl_total.setText(f"Total: PKR {total:.2f}")

    def save_purchase(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Validation", "Add at least one item to the purchase."); return
        supplier_index = self.cmb_supplier.currentIndex()
        supplier_id = self.cmb_supplier.itemData(supplier_index)
        supplier_name = self.cmb_supplier.currentText()
        # generate purchase_no: PCH-YYYYMMDD-XXXX
        todaycode = datetime.now().strftime("%Y%m%d")
        cur = self.db.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM purchases WHERE date_time LIKE ?", (f"{datetime.utcnow().strftime('%Y-%m-%d')}%",))
        seq = cur.fetchone()[0] + 1
        purchase_no = f"PCH-{todaycode}-{seq:04d}"
        # compute total
        total = 0.0
        items = []
        for r in range(self.table.rowCount()):
            barcode = self.table.item(r, 0).text()
            desc = self.table.item(r, 1).text()
            qty = int(self.table.item(r, 2).text())
            unit_price = float(self.table.item(r, 3).text())
            line_total = float(self.table.item(r, 4).text())
            prod_id = self.table.item(r, 5).text()
            prod_id = int(prod_id) if prod_id else None
            total += line_total
            items.append((prod_id, barcode, desc, qty, unit_price, line_total))
        try:
            # insert purchase
            cur.execute("INSERT INTO purchases (purchase_no, date_time, supplier_id, supplier_name, total_amount) VALUES (?, ?, ?, ?, ?)",
                        (purchase_no, datetime.utcnow().isoformat(), supplier_id, supplier_name, total))
            purchase_id = cur.lastrowid
            # insert purchase_items and update stock
            for (prod_id, barcode, desc, qty, unit_price, line_total) in items:
                cur.execute("INSERT INTO purchase_items (purchase_id, product_id, barcode, description, qty, unit_price, line_total) VALUES (?,?,?,?,?,?,?)",
                            (purchase_id, prod_id, barcode, desc, qty, unit_price, line_total))
                # update stock
                if prod_id:
                    try:
                        if hasattr(self.db, "increment_stock"):
                            self.db.increment_stock(prod_id, qty, new_cost=unit_price)
                        else:
                            cur.execute("UPDATE products SET stock_qty = stock_qty + ?, purchase_price = ? WHERE id=?", (qty, unit_price, prod_id))
                    except Exception:
                        pass
            self.db.conn.commit()
            QMessageBox.information(self, "Saved", f"Purchase {purchase_no} recorded.")
            self.accept()
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(self, "Error", f"Could not save purchase: {e}")
