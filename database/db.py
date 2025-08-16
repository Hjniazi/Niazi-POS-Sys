"""
database/db.py
Primary DB connection, minimal migrations & utility methods.

This DB class exposes helper methods used by the UI modules:
- settings (get_setting / set_setting)
- sales: create_sale, add_sale_item, list_sales_in_range, get_sale_items_for_sales
- purchases: create_purchase, add_purchase_item, list_purchases_by_supplier, get_purchase_items_for_purchases
- stock adjustments: decrement_stock, increment_stock
- suppliers: add_supplier, list_suppliers, find_supplier_by_name
- users: find_user, update_user_password
"""

import os
import sqlite3
from datetime import datetime, date
from .models import hash_password
from pathlib import Path

HERE = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(HERE, "schema.sql")

class DB:
    def __init__(self, filename="store.db"):
        self.filename = filename
        # ensure directory exists (if a path is given)
        db_dir = os.path.dirname(os.path.abspath(filename))
        if db_dir and not os.path.isdir(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self.conn = sqlite3.connect(self.filename, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._migrate()
        self._ensure_defaults()

    def _init_schema(self):
        # create tables if not exist using schema.sql
        if os.path.isfile(SCHEMA_PATH):
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema_sql = f.read()
        else:
            # fallback: minimal inline schema if file missing
            schema_sql = """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE,
                name TEXT NOT NULL,
                category TEXT,
                purchase_price REAL DEFAULT 0,
                sale_price REAL DEFAULT 0,
                stock_qty INTEGER DEFAULT 0,
                tax_percent REAL DEFAULT 0,
                reorder_level INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'cashier',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings ( key TEXT PRIMARY KEY, value TEXT );
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT UNIQUE,
                date_time TEXT,
                total_amount REAL,
                payment_method TEXT,
                paid_amount REAL,
                change_amount REAL,
                cashier_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER,
                product_id INTEGER,
                barcode TEXT,
                description TEXT,
                qty INTEGER,
                unit_price REAL,
                line_total REAL
            );
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_no TEXT UNIQUE,
                date_time TEXT,
                supplier_id INTEGER,
                supplier_name TEXT,
                total_amount REAL
            );
            CREATE TABLE IF NOT EXISTS purchase_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER,
                product_id INTEGER,
                barcode TEXT,
                description TEXT,
                qty INTEGER,
                unit_price REAL,
                line_total REAL
            );
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                contact TEXT,
                notes TEXT,
                created_at TEXT
            );
            """
        c = self.conn.cursor()
        c.executescript(schema_sql)
        self.conn.commit()

    def _migrate(self):
        # small idempotent migrations
        c = self.conn.cursor()
        # add reorder_level if missing
        try:
            c.execute("PRAGMA table_info(products)")
            cols = [r["name"] for r in c.fetchall()]
            if "reorder_level" not in cols:
                c.execute("ALTER TABLE products ADD COLUMN reorder_level INTEGER DEFAULT 0")
                self.conn.commit()
        except Exception:
            pass

    def _ensure_defaults(self):
        c = self.conn.cursor()
        defaults = {
            "store_name": "JADOON SHOPPING MART",
            "default_tax_percent": "0",
            "receipt_footer": "Thank you for shopping with Jadoon Shopping Mart!",
            "low_stock_threshold": "5"
        }
        for k, v in defaults.items():
            c.execute("SELECT value FROM settings WHERE key=?", (k,))
            if c.fetchone() is None:
                c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, v))
        # default admin
        c.execute("SELECT COUNT(*) as cnt FROM users")
        row = c.fetchone()
        if row is None or row["cnt"] == 0:
            now = datetime.utcnow().isoformat()
            salt_hex, hash_hex = hash_password("admin123")
            c.execute("INSERT INTO users (username, salt, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                      ("admin", salt_hex, hash_hex, "admin", now))
        self.conn.commit()

    # -----------------------
    # Settings helpers
    # -----------------------
    def get_setting(self, key, default=None):
        c = self.conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        r = c.fetchone()
        return r["value"] if r else default

    def set_setting(self, key, value):
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    # -----------------------
    # Sales helpers
    # -----------------------
    def create_sale(self, invoice_no, total_amount, payment_method, paid_amount, change_amount, cashier_id):
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        c.execute('''
            INSERT INTO sales (invoice_no, date_time, total_amount, payment_method, paid_amount, change_amount, cashier_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (invoice_no, now, total_amount, payment_method, paid_amount, change_amount, cashier_id))
        self.conn.commit()
        return c.lastrowid

    def add_sale_item(self, sale_id, product_id, barcode, desc, qty, unit_price, line_total):
        c = self.conn.cursor()
        c.execute('''
            INSERT INTO sale_items (sale_id, product_id, barcode, description, qty, unit_price, line_total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (sale_id, product_id, barcode, desc, qty, unit_price, line_total))
        self.conn.commit()

    def list_sales_in_range(self, start_date: date, end_date: date):
        c = self.conn.cursor()
        start_iso = start_date.isoformat()
        end_iso = end_date.isoformat()
        c.execute("SELECT * FROM sales WHERE date_time >= ? AND date_time <= ? ORDER BY date_time",
                  (start_iso + "T00:00:00", end_iso + "T23:59:59"))
        return c.fetchall()

    def get_sale_items_for_sales(self, sale_ids):
        if not sale_ids:
            return []
        c = self.conn.cursor()
        placeholders = ",".join("?" for _ in sale_ids)
        q = f"SELECT * FROM sale_items WHERE sale_id IN ({placeholders})"
        c.execute(q, tuple(sale_ids))
        return c.fetchall()

    # -----------------------
    # Purchases & suppliers
    # -----------------------
    def create_purchase(self, purchase_no, supplier_id, supplier_name, total_amount):
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        c.execute('''
            INSERT INTO purchases (purchase_no, date_time, supplier_id, supplier_name, total_amount)
            VALUES (?, ?, ?, ?, ?)
        ''', (purchase_no, now, supplier_id, supplier_name, total_amount))
        self.conn.commit()
        return c.lastrowid

    def add_purchase_item(self, purchase_id, product_id, barcode, desc, qty, unit_price, line_total):
        c = self.conn.cursor()
        c.execute('''
            INSERT INTO purchase_items (purchase_id, product_id, barcode, description, qty, unit_price, line_total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (purchase_id, product_id, barcode, desc, qty, unit_price, line_total))
        self.conn.commit()

    def list_purchases_by_supplier(self, supplier_id=None, start_date=None, end_date=None):
        c = self.conn.cursor()
        q = "SELECT * FROM purchases WHERE 1=1"
        params = []
        if supplier_id:
            q += " AND supplier_id=?"; params.append(supplier_id)
        if start_date:
            q += " AND date_time >= ?"; params.append(start_date.isoformat() + "T00:00:00")
        if end_date:
            q += " AND date_time <= ?"; params.append(end_date.isoformat() + "T23:59:59")
        q += " ORDER BY date_time"
        c.execute(q, tuple(params))
        return c.fetchall()

    def get_purchase_items_for_purchases(self, purchase_ids):
        if not purchase_ids:
            return []
        c = self.conn.cursor()
        placeholders = ",".join("?" for _ in purchase_ids)
        q = f"SELECT * FROM purchase_items WHERE purchase_id IN ({placeholders})"
        c.execute(q, tuple(purchase_ids))
        return c.fetchall()

    # Suppliers
    def add_supplier(self, name, contact="", notes=""):
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        c.execute("INSERT INTO suppliers (name, contact, notes, created_at) VALUES (?, ?, ?, ?)", (name, contact, notes, now))
        self.conn.commit()
        return c.lastrowid

    def list_suppliers(self):
        c = self.conn.cursor()
        c.execute("SELECT * FROM suppliers ORDER BY name")
        return c.fetchall()

    def find_supplier_by_name(self, name):
        c = self.conn.cursor()
        c.execute("SELECT * FROM suppliers WHERE name=?", (name,))
        return c.fetchone()

    # -----------------------
    # Stock helpers
    # -----------------------
    def decrement_stock(self, product_id, qty):
        if product_id is None:
            return
        c = self.conn.cursor()
        c.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id=?", (qty, product_id))
        self.conn.commit()

    def increment_stock(self, product_id, qty, new_cost=None):
        c = self.conn.cursor()
        if new_cost is not None:
            c.execute("UPDATE products SET stock_qty = stock_qty + ?, purchase_price = ? WHERE id=?", (qty, new_cost, product_id))
        else:
            c.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id=?", (qty, product_id))
        self.conn.commit()

    # -----------------------
    # Product helpers (optional convenience wrappers)
    # -----------------------
    def add_product(self, barcode, name, category, purchase_price, sale_price, stock_qty, tax_percent=0, reorder_level=0):
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        c.execute('''
            INSERT INTO products (barcode, name, category, purchase_price, sale_price, stock_qty, tax_percent, reorder_level, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (barcode, name, category, purchase_price, sale_price, stock_qty, tax_percent, reorder_level, now, now))
        self.conn.commit()
        return c.lastrowid

    def update_product(self, prod_id, barcode, name, category, purchase_price, sale_price, stock_qty, tax_percent=0, reorder_level=0):
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        c.execute('''
            UPDATE products SET barcode=?, name=?, category=?, purchase_price=?, sale_price=?, stock_qty=?, tax_percent=?, reorder_level=?, updated_at=?
            WHERE id=?
        ''', (barcode, name, category, purchase_price, sale_price, stock_qty, tax_percent, reorder_level, now, prod_id))
        self.conn.commit()

    def delete_product(self, prod_id):
        c = self.conn.cursor()
        c.execute("DELETE FROM products WHERE id=?", (prod_id,))
        self.conn.commit()

    def list_products(self):
        c = self.conn.cursor()
        c.execute("SELECT * FROM products ORDER BY name")
        return c.fetchall()

    def find_product_by_barcode(self, barcode):
        c = self.conn.cursor()
        c.execute("SELECT * FROM products WHERE barcode=?", (barcode,))
        return c.fetchone()

    def find_products_by_name(self, name_pattern):
        c = self.conn.cursor()
        pattern = f"%{name_pattern.lower()}%"
        c.execute("SELECT * FROM products WHERE LOWER(name) LIKE ? ORDER BY name", (pattern,))
        return c.fetchall()

    def get_product(self, prod_id):
        c = self.conn.cursor()
        c.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        return c.fetchone()

    # -----------------------
    # User helpers
    # -----------------------
    def find_user(self, username):
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        return c.fetchone()

    def update_user_password(self, username, new_password):
        salt_hex, hash_hex = hash_password(new_password)
        c = self.conn.cursor()
        c.execute("UPDATE users SET salt=?, password_hash=? WHERE username=?", (salt_hex, hash_hex, username))
        self.conn.commit()
