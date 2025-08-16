"""
ui/pos_window.py

POS window with robust suggestion handling:
- uses a suggestion->row map to avoid brittle text parsing
- reads popup.currentIndex() when handling Enter (safer)
- dedupe protection for quick duplicate events
- Delete shortcut and double-click qty editing
- Robust sale creation: uses DB-returned invoice when available, otherwise ensures invoice is set
"""

import time
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
    QSpinBox, QAction, QMessageBox, QDialog, QCompleter, QShortcut
)
from PyQt5.QtCore import Qt, QStringListModel, QTimer
from PyQt5.QtGui import QFont, QKeySequence

from ui.widgets import QtyDialog, ReceiptPreviewDialog
from reports.pdf_generator import save_receipt_pdf, format_receipt_text


class POSWindow(QMainWindow):
    def __init__(self, db, cashier_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.cashier_id = cashier_id or 1
        self.setWindowTitle("POS — Jadoon Shopping Mart")
        self.showFullScreen()

        # dedupe and suppression state
        self._ignore_next_return = False
        self._last_added_key = None
        self._last_added_time = 0.0
        self._dedupe_window = 0.6  # seconds

        # map suggestion string -> product row (sqlite3.Row)
        self._suggest_map = {}

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top_row = QHBoxLayout()
        lbl = QLabel("Barcode / Item Name:")
        lbl.setFont(QFont("Arial", 14))
        top_row.addWidget(lbl)

        # Search + completer
        self.input_search = QLineEdit()
        self.input_search.setFont(QFont("Arial", 14))
        self.input_search.setPlaceholderText("Scan barcode or type item name (suggestions)...")
        self.input_search.returnPressed.connect(self.on_scan_entered)
        top_row.addWidget(self.input_search)

        self.completer_model = QStringListModel()
        self.completer = QCompleter(self.completer_model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.input_search.setCompleter(self.completer)
        self.input_search.textEdited.connect(self.update_suggestions)
        # When a suggestion is activated (mouse click or keyboard enter) this fires
        self.completer.activated[str].connect(self.on_completer_activated)

        btn_add_manual = QPushButton("Add Manually")
        btn_add_manual.clicked.connect(self.add_item_manually)
        top_row.addWidget(btn_add_manual)
        layout.addLayout(top_row)

        # Cart table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Barcode", "Name", "Unit Price", "Qty", "Line Total"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        self.table.cellDoubleClicked.connect(self.on_table_double_click)

        # Bottom area
        bottom_row = QHBoxLayout()
        left = QVBoxLayout()
        self.lbl_subtotal = QLabel("Subtotal: PKR 0.00")
        self.lbl_total = QLabel("Total: PKR 0.00")
        self.lbl_subtotal.setFont(QFont("Arial", 14))
        self.lbl_total.setFont(QFont("Arial", 18))
        left.addWidget(self.lbl_subtotal)
        left.addWidget(self.lbl_total)
        bottom_row.addLayout(left)

        right = QVBoxLayout()
        self.btn_remove = QPushButton("Remove Selected Item")
        self.btn_remove.clicked.connect(self.remove_selected_item)
        self.btn_finalize = QPushButton("Complete Sale")
        self.btn_finalize.clicked.connect(self.complete_sale)
        self.input_paid = QDoubleSpinBox()
        self.input_paid.setPrefix("Paid PKR ")
        self.input_paid.setMaximum(10_000_000)
        self.input_paid.valueChanged.connect(self.update_change_display)
        right.addWidget(self.btn_remove)
        right.addWidget(QLabel("Paid Amount:"))
        right.addWidget(self.input_paid)
        right.addWidget(self.btn_finalize)
        bottom_row.addLayout(right)

        layout.addLayout(bottom_row)

        self.cart = []
        self.refresh_totals()

        # Delete shortcut
        QShortcut(QKeySequence("Delete"), self, activated=self.remove_selected_item)

        # Menu exit
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        exit_action = QAction("Exit POS", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    # ---------------- suggestions ----------------
    def update_suggestions(self, text):
        t = (text or "").strip()
        try:
            if not t:
                rows = self.db.conn.execute("SELECT name, barcode, id FROM products ORDER BY name").fetchall()
            else:
                pat = f"%{t.lower()}%"
                rows = self.db.conn.execute(
                    "SELECT name, barcode, id FROM products WHERE LOWER(name) LIKE ? OR barcode LIKE ? ORDER BY name",
                    (pat, f"%{t}%")
                ).fetchall()
        except Exception:
            rows = []

        suggestions = []
        self._suggest_map.clear()
        seen = set()
        for r in rows:
            name = (r["name"] or "").strip()
            barcode = (r["barcode"] or "").strip()
            label = name
            if barcode:
                label = f"{name} — {barcode}"
            # avoid duplicates
            if label in seen:
                continue
            seen.add(label)
            suggestions.append(label)
            # store the full product row for this label (we'll query full row when used)
            try:
                full = self.db.conn.execute("SELECT * FROM products WHERE id=? LIMIT 1", (r["id"],)).fetchone()
                self._suggest_map[label] = full
            except Exception:
                self._suggest_map[label] = r

        self.completer_model.setStringList(suggestions)

    def on_completer_activated(self, text):
        # prefer map lookup (robust)
        if not text:
            return
        row = self._suggest_map.get(text)
        if row is None:
            # fallback: try to search DB by full text
            parts = text.split("—")
            barcode = None
            name = text.strip()
            if len(parts) >= 2:
                name = parts[0].strip()
                barcode = parts[1].strip()
            if barcode:
                row = self.db.conn.execute("SELECT * FROM products WHERE barcode=? LIMIT 1", (barcode,)).fetchone()
            if not row and name:
                row = self.db.conn.execute("SELECT * FROM products WHERE LOWER(name)=? LIMIT 1", (name.lower(),)).fetchone()
            if not row:
                row = self.db.conn.execute(
                    "SELECT * FROM products WHERE LOWER(name) LIKE ? OR barcode LIKE ? ORDER BY name LIMIT 1",
                    (f"%{name.lower()}%", f"%{name}%")
                ).fetchone()

        if row:
            # dedupe guard will ignore duplicate rapid events
            self._add_product_row(row)
            # mark last added
            try:
                pid = row["id"]
                bc = row["barcode"] or ""
                nm = row["name"] or ""
            except Exception:
                pid = None; bc = ""; nm = ""
            self._set_last_added(pid, bc, nm)
            # clear search and refocus
            self.input_search.clear()
            self.input_search.setFocus()
            # small suppression to avoid immediate returnPressed firing
            self._ignore_next_return = True
            QTimer.singleShot(350, lambda: setattr(self, "_ignore_next_return", False))
        else:
            QMessageBox.information(self, "Not Found", "Product not found.")
            self.input_search.clear()
            self.input_search.setFocus()

    # ---------------- Enter/scan handler ----------------
    def on_scan_entered(self):
        # suppression flag: ignore the return if set by completer activation
        if getattr(self, "_ignore_next_return", False):
            # reset and ignore this Enter key
            self._ignore_next_return = False
            self.input_search.clear()
            self.input_search.setFocus()
            return

        # if popup visible, attempt to read popup.currentIndex() first (reliable for keyboard selection)
        popup = self.completer.popup()
        if popup is not None and popup.isVisible():
            idx = popup.currentIndex()
            if idx.isValid():
                # request display role explicitly
                current = idx.data(Qt.DisplayRole)
                if current:
                    # route to the same handler used by completer
                    self.on_completer_activated(str(current))
                    return
            # fallback to completer.currentCompletion() (string)
            current = self.completer.currentCompletion()
            if current:
                self.on_completer_activated(current)
                return

        text = self.input_search.text().strip()
        if not text:
            return

        # try barcode exact
        row = self.db.conn.execute("SELECT * FROM products WHERE barcode=? LIMIT 1", (text,)).fetchone()
        if not row:
            # try exact name
            row = self.db.conn.execute("SELECT * FROM products WHERE LOWER(name)=? LIMIT 1", (text.lower(),)).fetchone()
        if not row:
            # partial match
            row = self.db.conn.execute(
                "SELECT * FROM products WHERE LOWER(name) LIKE ? OR barcode LIKE ? ORDER BY name LIMIT 1",
                (f"%{text.lower()}%", f"%{text}%")
            ).fetchone()

        if row:
            self._add_product_row(row)
        else:
            QMessageBox.warning(self, "Not Found", "Product not found. Please register it in Admin Panel.")

        self.input_search.clear()
        self.input_search.setFocus()

    # ---------------- dedupe helpers ----------------
    def _make_key(self, product_id, barcode, name):
        pid_part = str(product_id) if product_id is not None else ""
        bc_part = (barcode or "").strip()
        name_part = (name or "").strip().lower()
        return f"{pid_part}|{bc_part}|{name_part}"

    def _set_last_added(self, product_id, barcode, name):
        self._last_added_key = self._make_key(product_id, barcode, name)
        self._last_added_time = time.time()

    def _is_recent_duplicate(self, product_id, barcode, name):
        key = self._make_key(product_id, barcode, name)
        if self._last_added_key is None:
            return False
        if key != self._last_added_key:
            return False
        if (time.time() - self._last_added_time) <= self._dedupe_window:
            return True
        return False

    # ---------------- actual add ----------------
    def _add_product_row(self, row_or_data):
        if row_or_data is None:
            return

        # Normalize row to fields
        try:
            prod_id = int(row_or_data["id"]) if row_or_data["id"] is not None else None
            barcode = (row_or_data["barcode"] or "").strip()
            name = (row_or_data["name"] or "").strip()
            unit_price = float(row_or_data["sale_price"] or 0.0)
        except Exception:
            prod_id = row_or_data.get("product_id") if isinstance(row_or_data, dict) else None
            barcode = (row_or_data.get("barcode") or "").strip() if isinstance(row_or_data, dict) else ""
            name = (row_or_data.get("name") or "").strip() if isinstance(row_or_data, dict) else ""
            # try multiple keys for unit price in different contexts
            unit_price = 0.0
            if isinstance(row_or_data, dict):
                unit_price = float(row_or_data.get("sale_price") or row_or_data.get("unit_price") or 0.0)

        # Deduplicate rapid double events
        if self._is_recent_duplicate(prod_id, barcode, name):
            self.input_search.clear()
            self.input_search.setFocus()
            return

        # try to find existing cart item
        matched = None
        if prod_id is not None:
            for item in self.cart:
                if item.get("product_id") == prod_id:
                    matched = item
                    break
        if matched is None and barcode:
            for item in self.cart:
                if item.get("barcode") and item.get("barcode") == barcode:
                    matched = item
                    break
        if matched is None and name:
            for item in self.cart:
                if item.get("name") and item.get("name").lower() == name.lower():
                    matched = item
                    break

        if matched:
            matched["qty"] += 1
            matched["line_total"] = matched["qty"] * matched["unit_price"]
        else:
            item = {
                "product_id": prod_id,
                "barcode": barcode,
                "name": name,
                "unit_price": unit_price,
                "qty": 1,
                "line_total": unit_price * 1
            }
            self.cart.append(item)

        # record as last added
        self._set_last_added(prod_id, barcode, name)
        self.input_search.clear()
        self.input_search.setFocus()
        self.refresh_cart_table()

    # ---------------- manual add ----------------
    def add_item_manually(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Item Manually")
        from PyQt5.QtWidgets import QFormLayout, QDoubleSpinBox, QSpinBox, QLineEdit, QPushButton
        form = QFormLayout(dlg)
        txt_barcode = QLineEdit()
        txt_name = QLineEdit()
        spin_price = QDoubleSpinBox(); spin_price.setPrefix("PKR "); spin_price.setMaximum(1_000_000)
        spin_qty = QSpinBox(); spin_qty.setMaximum(10000); spin_qty.setValue(1)
        form.addRow("Barcode:", txt_barcode)
        form.addRow("Name:", txt_name)
        form.addRow("Unit Price:", spin_price)
        form.addRow("Qty:", spin_qty)
        btn = QPushButton("Add")
        form.addRow(btn)
        btn.clicked.connect(lambda: dlg.accept())
        if dlg.exec_() == QDialog.Accepted:
            barcode = txt_barcode.text().strip()
            name = txt_name.text().strip()
            price = float(spin_price.value())
            qty = int(spin_qty.value())
            if not name or price <= 0 or qty <= 0:
                QMessageBox.warning(self, "Validation", "Enter name, positive price and qty.")
                return
            added = False
            if barcode:
                for it in self.cart:
                    if it.get("barcode") and it.get("barcode") == barcode:
                        it["qty"] += qty
                        it["line_total"] = it["qty"] * it["unit_price"]
                        added = True
                        break
            if not added:
                for it in self.cart:
                    if it.get("product_id") is None and it.get("name").lower() == name.lower():
                        it["qty"] += qty
                        it["line_total"] = it["qty"] * it["unit_price"]
                        added = True
                        break
            if not added:
                item = {
                    "product_id": None,
                    "barcode": barcode,
                    "name": name,
                    "unit_price": price,
                    "qty": qty,
                    "line_total": price * qty
                }
                self.cart.append(item)
            self._set_last_added(None, barcode, name)
            self.input_search.clear()
            self.input_search.setFocus()
            self.refresh_cart_table()

    # ---------------- table and totals ----------------
    def refresh_cart_table(self):
        self.table.setRowCount(0)
        for it in self.cart:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(it.get("barcode") or ""))
            self.table.setItem(r, 1, QTableWidgetItem(it["name"]))
            self.table.setItem(r, 2, QTableWidgetItem(f"{it['unit_price']:.2f}"))
            self.table.setItem(r, 3, QTableWidgetItem(str(it["qty"])))
            self.table.setItem(r, 4, QTableWidgetItem(f"{it['line_total']:.2f}"))
        self.refresh_totals()

    def refresh_totals(self):
        subtotal = sum(it["line_total"] for it in self.cart)
        self.lbl_subtotal.setText(f"Subtotal: PKR {subtotal:.2f}")
        self.lbl_total.setText(f"Total: PKR {subtotal:.2f}")
        self.update_change_display()

    def update_change_display(self):
        subtotal = sum(it["line_total"] for it in self.cart)
        paid = float(self.input_paid.value())
        change = paid - subtotal
        self.setWindowTitle(f"POS — Change: PKR {change:.2f}")
        if change >= 0:
            self.lbl_total.setText(f"Total: PKR {subtotal:.2f}   Change: PKR {change:.2f}")
        else:
            self.lbl_total.setText(f"Total: PKR {subtotal:.2f}   Due: PKR {abs(change):.2f}")

    def on_table_double_click(self, row, col):
        if col != 3:
            return
        try:
            current_qty = int(self.table.item(row, 3).text())
        except Exception:
            current_qty = 1
        dlg = QtyDialog(current=current_qty, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            new_q = dlg.get_value()
            if 0 <= row < len(self.cart):
                self.cart[row]["qty"] = new_q
                self.cart[row]["line_total"] = new_q * self.cart[row]["unit_price"]
                self.refresh_cart_table()

    def remove_selected_item(self):
        row = self.table.currentRow()
        if row < 0:
            return
        if 0 <= row < len(self.cart):
            del self.cart[row]
        self.refresh_cart_table()

    # ---------------- complete sale ----------------
    def complete_sale(self):
        if not self.cart:
            QMessageBox.warning(self, "Empty", "Cart is empty.")
            return
        subtotal = sum(it["line_total"] for it in self.cart)
        paid = float(self.input_paid.value())
        if paid < subtotal:
            confirm = QMessageBox.question(self, "Insufficient Paid", "Paid amount is less than total. Continue anyway?")
            if confirm != QMessageBox.Yes:
                return

        # Prefer letting DB generate a unique invoice. Pass None so DB can decide.
        change_amount = max(0, paid - subtotal)
        try:
            ret = self.db.create_sale(None, subtotal, "CASH", paid, change_amount, self.cashier_id)
        except Exception as e:
            # If DB create_sale raised unexpectedly, inform and abort
            QMessageBox.critical(self, "Error", f"Could not create sale: {e}")
            return

        # Normalize return: handle both (sale_id, invoice_no) and sale_id-only implementations
        sale_id = None
        actual_invoice_no = None
        try:
            if isinstance(ret, (tuple, list)) and len(ret) >= 2:
                sale_id, actual_invoice_no = ret[0], ret[1]
            else:
                sale_id = int(ret)
                # try to fetch invoice_no from DB row
                row = self.db.conn.execute("SELECT invoice_no FROM sales WHERE id=?", (sale_id,)).fetchone()
                if row and row["invoice_no"]:
                    actual_invoice_no = row["invoice_no"]
                else:
                    # fallback: create a stable invoice based on id + date and update DB
                    actual_invoice_no = f"JSM-{datetime.utcnow().strftime('%Y%m%d')}-{sale_id:06d}"
                    try:
                        self.db.conn.execute("UPDATE sales SET invoice_no=? WHERE id=?", (actual_invoice_no, sale_id))
                        self.db.conn.commit()
                    except Exception:
                        # ignore update errors; we still proceed using generated invoice string
                        pass
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Unexpected create_sale return: {ex}")
            return

        # store sale items and adjust stock
        for it in self.cart:
            pid = it.get("product_id")
            barcode = it.get("barcode") or ""
            desc = it["name"]
            qty = int(it["qty"])
            unit_price = float(it["unit_price"])
            line_total = float(it["line_total"])
            try:
                self.db.add_sale_item(sale_id, pid, barcode, desc, qty, unit_price, line_total)
            except Exception:
                # continue adding others even if one fails — but log/show if needed
                pass
            if pid:
                try:
                    self.db.decrement_stock(pid, qty)
                except Exception:
                    pass

        # Generate receipt using actual invoice number returned by DB
        store_name = self.db.get_setting("store_name", "JADOON SHOPPING MART")
        footer = self.db.get_setting("receipt_footer", "Thank you for shopping with Jadoon Shopping Mart!")
        try:
            receipt_path = save_receipt_pdf(store_name, actual_invoice_no, self.cart, subtotal, paid, change_amount, footer)
        except Exception:
            # if PDF generator is not available, fallback to text via format_receipt_text
            try:
                receipt_text = format_receipt_text(store_name, actual_invoice_no, self.cart, subtotal, paid, change_amount, footer)
                # save text file
                import os
                os.makedirs("receipts", exist_ok=True)
                path_txt = os.path.join("receipts", f"{actual_invoice_no}.txt")
                with open(path_txt, "w", encoding="utf-8") as f:
                    f.write(receipt_text)
                receipt_path = path_txt
            except Exception:
                receipt_path = "N/A"

        # prepare receipt preview text
        try:
            receipt_text = format_receipt_text(store_name, actual_invoice_no, self.cart, subtotal, paid, change_amount, footer)
        except Exception:
            receipt_text = f"Invoice {actual_invoice_no}\nReceipt saved at: {receipt_path}"

        dlg = ReceiptPreviewDialog(f"Receipt — {actual_invoice_no}", receipt_text, parent=self)
        dlg.exec_()

        QMessageBox.information(self, "Sale Completed", f"Invoice {actual_invoice_no} saved.\nReceipt: {receipt_path}")
        # Reset cart & paid
        self.cart = []
        self.input_paid.setValue(0)
        self.refresh_cart_table()
