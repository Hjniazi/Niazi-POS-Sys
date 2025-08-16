"""
database/models.py
CRUD helpers and domain operations.
"""
import sqlite3
import binascii
import hashlib
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple


# --- Password utilities ---
def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200_000)
    return binascii.hexlify(salt).decode(), binascii.hexlify(dk).decode()


def verify_password(salt_hex: str, hash_hex: str, provided_password: str) -> bool:
    salt = binascii.unhexlify(salt_hex.encode())
    dk = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 200_000)
    return binascii.hexlify(dk).decode() == hash_hex


# --- Product helpers ---
def add_product(conn: sqlite3.Connection, barcode, name, category,
                purchase_price, sale_price, stock_qty, tax_percent=0, reorder_level=0) -> int:
    now = datetime.utcnow().isoformat()
    c = conn.cursor()
    c.execute(
        """INSERT INTO products
           (barcode, name, category, purchase_price, sale_price, stock_qty, tax_percent, reorder_level, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (barcode, name, category, purchase_price, sale_price, stock_qty, tax_percent, reorder_level, now, now),
    )
    conn.commit()
    return c.lastrowid


def update_product(conn: sqlite3.Connection, pid: int, **fields):
    if not fields:
        return
    fields["updated_at"] = datetime.utcnow().isoformat()
    keys = ", ".join([f"{k}=?" for k in fields.keys()])
    vals = list(fields.values()) + [pid]
    conn.execute(f"UPDATE products SET {keys} WHERE id=?", vals)
    conn.commit()


def delete_product(conn: sqlite3.Connection, pid: int):
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()


def find_product_by_barcode(conn: sqlite3.Connection, barcode: str):
    return conn.execute("SELECT * FROM products WHERE barcode=?", (barcode,)).fetchone()


def change_stock(conn: sqlite3.Connection, pid: int, delta_qty: int):
    conn.execute("UPDATE products SET stock_qty = stock_qty + ?, updated_at=? WHERE id=?", (delta_qty, datetime.utcnow().isoformat(), pid))
    conn.commit()


# --- Supplier helpers ---
def upsert_supplier(conn: sqlite3.Connection, name: str, contact: str = "", notes: str = "") -> int:
    row = conn.execute("SELECT id FROM suppliers WHERE name=?", (name,)).fetchone()
    now = datetime.utcnow().isoformat()
    if row:
        conn.execute("UPDATE suppliers SET contact=?, notes=? WHERE id=?", (contact, notes, row["id"]))
        conn.commit()
        return row["id"]
    conn.execute("INSERT INTO suppliers (name, contact, notes, created_at) VALUES (?, ?, ?, ?)",
                 (name, contact, notes, now))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# --- Sales helpers ---
def create_sale(conn: sqlite3.Connection, items: List[Dict], payment_method: str,
                paid_amount: float, change_amount: float, cashier_id: Optional[int]) -> str:
    """
    items: list of dicts -> {'product_id', 'barcode', 'name', 'qty', 'unit_price', 'line_total'}
    """
    c = conn.cursor()
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # invoice number (simple incremental)
    c.execute("SELECT IFNULL(MAX(id), 0) + 1 FROM sales")
    next_id = c.fetchone()[0]
    invoice_no = f"INV-{next_id:06d}"
    total_amount = sum(i["line_total"] for i in items)
    c.execute("""INSERT INTO sales (invoice_no, date_time, total_amount, payment_method, paid_amount, change_amount, cashier_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (invoice_no, dt, total_amount, payment_method, paid_amount, change_amount, cashier_id))
    sale_id = c.lastrowid
    for it in items:
        c.execute("""INSERT INTO sale_items (sale_id, product_id, barcode, description, qty, unit_price, line_total)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (sale_id, it["product_id"], it["barcode"], it["name"], it["qty"], it["unit_price"], it["line_total"]))
        # reduce stock
        c.execute("UPDATE products SET stock_qty = stock_qty - ?, updated_at=? WHERE id=?",
                  (it["qty"], datetime.utcnow().isoformat(), it["product_id"]))
    conn.commit()
    return invoice_no


# --- Purchase helpers ---
def create_purchase(conn: sqlite3.Connection, supplier_id: Optional[int], supplier_name: str, items: List[Dict]) -> str:
    c = conn.cursor()
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT IFNULL(MAX(id), 0) + 1 FROM purchases")
    next_id = c.fetchone()[0]
    purchase_no = f"PUR-{next_id:06d}"
    total_amount = sum(i["line_total"] for i in items)
    c.execute("""INSERT INTO purchases (purchase_no, date_time, supplier_id, supplier_name, total_amount)
                 VALUES (?, ?, ?, ?, ?)""",
              (purchase_no, dt, supplier_id, supplier_name, total_amount))
    purchase_id = c.lastrowid
    for it in items:
        c.execute("""INSERT INTO purchase_items (purchase_id, product_id, barcode, description, qty, unit_price, line_total)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (purchase_id, it["product_id"], it["barcode"], it["name"], it["qty"], it["unit_price"], it["line_total"]))
        # increase stock
        c.execute("UPDATE products SET stock_qty = stock_qty + ?, updated_at=? WHERE id=?",
                  (it["qty"], datetime.utcnow().isoformat(), it["product_id"]))
    conn.commit()
    return purchase_no
