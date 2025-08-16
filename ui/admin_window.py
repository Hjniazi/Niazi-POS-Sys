"""
ui/admin_window.py
Admin dashboard: card-like animated buttons with icons.
- Header now uses Times New Roman, larger size.
- Hint is pinned to the bottom of the page.
- Includes 'Open POS' button; Suppliers module removed.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout, QMessageBox
)
# QGraphicsDropShadowEffect is under QtWidgets in PyQt5
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QPoint
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor

from ui.product_management import ProductManagementWindow
from ui.purchase_entry import PurchaseEntryDialog
from ui.inventory_view import InventoryDialog
from ui.sales_analytics import AnalyticsWindow
from ui.supplier_ledger import SupplierLedgerDialog
from ui.settings_window import SettingsWindow
from ui.pos_window import POSWindow
from ui.receipt_history import ReceiptHistoryDialog


# ---------- Fancy card-like animated button ----------
class CardButton(QPushButton):
    """
    A QPushButton with:
    - Drop shadow (3D card look)
    - Icon + label
    - Press animation (tiny downward translation)
    """
    def __init__(self, text: str, icon_path: str = "", parent=None):
        super().__init__(text, parent)
        self._base_pos = None

        # Styling: rounded card-like look
        self.setMinimumSize(180, 120)
        self.setIconSize(QSize(48, 48))
        self.setFont(QFont("Arial", 11, QFont.Bold))
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #fafafa, stop:1 #e9eef5);
                border: 1px solid #c9d3e0;
                border-radius: 16px;
                padding: 14px;
                color: #1b2b49;
                text-align: left;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #ffffff, stop:1 #eef3fb);
            }
            QPushButton:pressed {
                background: #e8edf5;
            }
        """)

        # Optional icon
        if icon_path:
            icon = QIcon()
            pix = QPixmap(icon_path)
            if not pix.isNull():
                icon.addPixmap(pix)
                self.setIcon(icon)

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

        # Press animation
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(90)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def mousePressEvent(self, event):
        if self._base_pos is None:
            self._base_pos = self.pos()
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self._base_pos + QPoint(0, 3))
        self._anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self._base_pos)
        self._anim.start()
        super().mouseReleaseEvent(event)


class AdminWindow(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Admin Panel")
        self.resize(1100, 720)

        root = QVBoxLayout(self)

        # Header: Times New Roman, larger size
        header = QLabel("Admin Panel — Jadoon Shopping Mart")
        header.setFont(QFont("Times New Roman", 24, QFont.Bold))
        header.setAlignment(Qt.AlignLeft)
        header.setStyleSheet("margin-bottom: 6px; color: #1b2b49;")
        root.addWidget(header)

        # Grid of action buttons
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        root.addLayout(grid)

        # Helper for creating card buttons with icons in /assets/icons
        def add_btn(row, col, text, icon_name, handler):
            icon_path = f"assets/icons/{icon_name}"
            btn = CardButton(text, icon_path)
            btn.clicked.connect(handler)
            grid.addWidget(btn, row, col)
            return btn

        # Row 0
        self.btn_open_pos = add_btn(0, 0, "Open POS", "pos.png", self.open_pos)
        self.btn_products = add_btn(0, 1, "Products", "products.png", self.open_products)
        self.btn_purchase = add_btn(0, 2, "Purchase Entry", "purchase.png", self.open_purchase)

        # Row 1
        self.btn_inventory = add_btn(1, 0, "Inventory", "inventory.png", self.open_inventory)
        self.btn_analytics = add_btn(1, 1, "Sales Analytics", "analytics.png", self.open_analytics)
        self.btn_supplier_ledger = add_btn(1, 2, "Supplier Ledger", "ledger.png", self.open_supplier_ledger)

        # Row 2
        self.btn_settings = add_btn(2, 1, "Settings", "settings.png", self.open_settings)
        self.btn_receipts = add_btn(2, 0, "Receipt History", "receipts.png", self.open_receipts)

        # Add a stretch so the hint is pushed to the very bottom
        root.addStretch(1)

        # Bottom hint
        hint = QLabel("Tip: You can also launch the POS directly from here.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:#50607a; padding: 8px;")
        root.addWidget(hint)

        # Keep references so windows don't get garbage collected
        self._open_windows = {}

    # ---------- Handlers ----------
    def open_pos(self):
        try:
            rows = self.db.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if rows == 0:
                QMessageBox.warning(self, "No Products", "No products registered. Please add products first.")
                return
            win = POSWindow(self.db)
            win.show()
            self._open_windows["pos"] = win
        except Exception as e:
            QMessageBox.critical(self, "Open POS Failed", f"Could not open POS window:\n{e}")

    def open_products(self):
        try:
            win = ProductManagementWindow(self.db)
            win.show()
            self._open_windows["products"] = win
        except Exception as e:
            QMessageBox.critical(self, "Open Products Failed", f"Could not open Product Management:\n{e}")

    def open_purchase(self):
        try:
            dlg = PurchaseEntryDialog(self.db, parent=self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Open Purchase Entry Failed", f"Could not open Purchase Entry:\n{e}")

    def open_inventory(self):
        try:
            dlg = InventoryDialog(self.db, parent=self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Open Inventory Failed", f"Could not open Inventory:\n{e}")

    def open_analytics(self):
        try:
            win = AnalyticsWindow(self.db)
            win.show()
            self._open_windows["analytics"] = win
        except Exception as e:
            QMessageBox.critical(self, "Open Analytics Failed", f"Could not open Sales Analytics:\n{e}")

    def open_supplier_ledger(self):
        try:
            dlg = SupplierLedgerDialog(self.db, parent=self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Open Supplier Ledger Failed", f"Could not open Supplier Ledger:\n{e}")

    def open_settings(self):
        try:
            win = SettingsWindow(self.db, parent=self)
            # Works whether SettingsWindow is a QWidget or QDialog
            if hasattr(win, "exec_"):
                win.exec_()
            else:
                win.show()
                self._open_windows["settings"] = win
        except TypeError:
            # Fallback for SettingsWindow without parent kwarg
            try:
                win = SettingsWindow(self.db)
                if hasattr(win, "exec_"):
                    win.exec_()
                else:
                    win.show()
                    self._open_windows["settings"] = win
            except Exception as e:
                QMessageBox.critical(self, "Open Settings Failed", f"Could not open Settings:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Open Settings Failed", f"Could not open Settings:\n{e}")

    def open_receipts(self):
        try:
            dlg = ReceiptHistoryDialog(self.db, parent=self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Open Receipt History Failed", f"Could not open Receipt History:\n{e}")
