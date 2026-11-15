import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shop_bot.db')

def init_db():
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
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            photo_id TEXT,
            full_photo_id TEXT
        )
    ''')
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

def add_product(name, price, photo_id, full_photo_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO products (name, price, photo_id, full_photo_id) VALUES (?, ?, ?, ?)', (name, price, photo_id, full_photo_id))
    conn.commit()
    conn.close()

def get_products():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, photo_id, full_photo_id FROM products')
    products = cursor.fetchall()
    conn.close()
    return products

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

init_db()