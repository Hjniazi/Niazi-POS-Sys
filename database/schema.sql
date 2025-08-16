-- schema.sql: Creates all tables
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

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

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
