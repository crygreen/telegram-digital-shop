import sqlite3
import os
from contextlib import closing
from pathlib import Path
from uuid import uuid4

DB_PATH = os.getenv('DB_PATH') or str(Path(__file__).with_name('shop_bot.db'))

def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            language TEXT DEFAULT 'ru',
            is_admin INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price_rub INTEGER,
        price_stars INTEGER
    )
''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            price_rub INTEGER,
            price_stars INTEGER,
            photo_id TEXT,
            full_photo_id TEXT
        )
    ''')
    cursor.execute('PRAGMA table_info(products)')
    product_columns = [column[1] for column in cursor.fetchall()]
    if 'price_rub' not in product_columns:
        cursor.execute('ALTER TABLE products ADD COLUMN price_rub INTEGER')
    if 'price_stars' not in product_columns:
        cursor.execute('ALTER TABLE products ADD COLUMN price_stars INTEGER')
    if 'delivery_kind' not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN delivery_kind TEXT NOT NULL DEFAULT 'photo'")
    cursor.execute('UPDATE products SET price_rub = price WHERE price_rub IS NULL')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_links (
            admin_msg_id INTEGER PRIMARY KEY,
            client_id INTEGER
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('status', 'offline')")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS card_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price_rub INTEGER NOT NULL CHECK (price_rub > 0),
            full_photo_id TEXT NOT NULL,
            receipt_id TEXT,
            receipt_type TEXT,
            status TEXT NOT NULL DEFAULT 'awaiting_receipt',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS active_card_order
        ON card_orders (user_id, product_id)
        WHERE status IN ('awaiting_receipt', 'submitted', 'delivering', 'delivery_failed')
    ''')
    card_columns = [row[1] for row in cursor.execute('PRAGMA table_info(card_orders)')]
    if 'delivery_kind' not in card_columns:
        cursor.execute("ALTER TABLE card_orders ADD COLUMN delivery_kind TEXT NOT NULL DEFAULT 'photo'")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS star_orders (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            amount INTEGER NOT NULL CHECK (amount > 0),
            file_id TEXT NOT NULL,
            delivery_kind TEXT NOT NULL,
            mode TEXT NOT NULL,
            checkout_id TEXT,
            charge_id TEXT UNIQUE,
            status TEXT NOT NULL DEFAULT 'created',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

def set_language(user_id, lang):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET language = ? WHERE id = ?', (lang, user_id))
    conn.commit()
    conn.close()

def get_language(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT language FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'ru'

def add_product(name, price_rub, price_stars, photo_id, full_photo_id, delivery_kind='photo'):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO products (name, price, price_rub, price_stars, photo_id, full_photo_id, delivery_kind)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (name, price_rub, price_rub, price_stars, photo_id, full_photo_id, delivery_kind)
    )
    conn.commit()
    conn.close()

def add_template(name, price_rub, price_stars):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO templates (name, price_rub, price_stars) VALUES (?, ?, ?)',
        (name, price_rub, price_stars)
    )
    conn.commit()
    conn.close()

def get_templates():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price_rub, price_stars FROM templates')
    templates = cursor.fetchall()
    conn.close()
    return templates

def get_template(template_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, name, price_rub, price_stars FROM templates WHERE id = ?',
        (template_id,)
    )
    template = cursor.fetchone()
    conn.close()
    return template

def get_products():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price_rub, price_stars, photo_id, full_photo_id FROM products')
    products = cursor.fetchall()
    conn.close()
    return products

def get_product(product_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, name, price_rub, price_stars, photo_id, full_photo_id FROM products WHERE id = ?',
        (product_id,)
    )
    product = cursor.fetchone()
    conn.close()
    return product


def get_delivery_kind(product_id):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        row = conn.execute('SELECT delivery_kind FROM products WHERE id = ?', (product_id,)).fetchone()
    return row[0] if row else 'photo'

def get_status():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'status'")
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 'offline'

def set_status(status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'status'", (status,))
    conn.commit()
    conn.close()

def save_chat_link(admin_msg_id, client_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO chat_links (admin_msg_id, client_id) VALUES (?, ?)', (admin_msg_id, client_id))
    conn.commit()
    conn.close()

def get_client_by_admin_msg(admin_msg_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT client_id FROM chat_links WHERE admin_msg_id = ?', (admin_msg_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def create_card_order(user_id, product):
    product_id, name, price_rub, _, _, full_photo_id = product
    if not isinstance(price_rub, int) or price_rub <= 0 or not full_photo_id:
        raise ValueError('Product needs a positive price and a delivery file')
    conn = sqlite3.connect(DB_PATH)
    delivery_kind = get_delivery_kind(product_id)
    try:
        with conn:
            conn.execute('''
                INSERT OR IGNORE INTO card_orders
                (user_id, product_id, product_name, price_rub, full_photo_id, delivery_kind)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, product_id, name, price_rub, full_photo_id, delivery_kind))
            row = conn.execute('''
                SELECT id FROM card_orders WHERE user_id = ? AND product_id = ?
                AND status IN ('awaiting_receipt', 'submitted', 'delivering', 'delivery_failed')
            ''', (user_id, product_id)).fetchone()
            return row[0]
    finally:
        conn.close()

def get_card_order(order_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('SELECT * FROM card_orders WHERE id = ?', (order_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def submit_card_receipt(order_id, user_id, receipt_id, receipt_type):
    if receipt_type not in ('photo', 'document'):
        raise ValueError('Unsupported receipt type')
    conn = sqlite3.connect(DB_PATH)
    try:
        with conn:
            result = conn.execute('''
                UPDATE card_orders SET receipt_id = ?, receipt_type = ?, status = 'submitted'
                WHERE id = ? AND user_id = ? AND status = 'awaiting_receipt'
            ''', (receipt_id, receipt_type, order_id, user_id))
            return result.rowcount == 1
    finally:
        conn.close()

def change_card_order_status(order_id, expected, new_status):
    conn = sqlite3.connect(DB_PATH)
    try:
        with conn:
            result = conn.execute(
                'UPDATE card_orders SET status = ? WHERE id = ? AND status = ?',
                (new_status, order_id, expected)
            )
            return result.rowcount == 1
    finally:
        conn.close()

def get_pending_card_orders():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute('''
            SELECT * FROM card_orders WHERE status IN ('submitted', 'delivery_failed', 'delivering')
            ORDER BY id
        ''').fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def create_star_order(user_id, product, mode):
    product_id, name, _, amount, _, file_id = product
    order_id = uuid4().hex
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute('''
            INSERT INTO star_orders (id, user_id, product_id, product_name, amount, file_id, delivery_kind, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_id, user_id, product_id, name, amount, file_id, get_delivery_kind(product_id), mode))
    return order_id


def authorize_star_checkout(order_id, user_id, amount, checkout_id):
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        result = conn.execute('''
            UPDATE star_orders SET status = 'checkout', checkout_id = ?
            WHERE id = ? AND user_id = ? AND amount = ? AND mode = 'telegram_test'
            AND (status = 'created' OR (status = 'checkout' AND checkout_id = ?))
        ''', (checkout_id, order_id, user_id, amount, checkout_id))
        return result.rowcount == 1


def record_star_payment(order_id, user_id, amount, charge_id, mode):
    expected = 'created' if mode == 'demo' else 'checkout'
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        result = conn.execute('''
            UPDATE OR IGNORE star_orders SET charge_id = ?, status = 'paid'
            WHERE id = ? AND user_id = ? AND amount = ? AND mode = ? AND status = ? AND charge_id IS NULL
        ''', (charge_id, order_id, user_id, amount, mode, expected))
        return result.rowcount == 1


def get_star_order(order_id):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute('SELECT * FROM star_orders WHERE id = ?', (order_id,)).fetchone()


def change_star_order_status(order_id, expected, status):
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        result = conn.execute('''
            UPDATE star_orders SET status = ? WHERE id = ? AND status = ? AND charge_id IS NOT NULL
        ''', (status, order_id, expected))
        return result.rowcount == 1
