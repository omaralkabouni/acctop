import sqlite3
import os

db_path = os.path.join('instance', 'erp_top.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN image VARCHAR(300)")
        print("Column 'image' added to 'products' table.")
    except sqlite3.OperationalError as e:
        print(f"Error or column already exists: {e}")
    conn.commit()
    conn.close()
else:
    print(f"Database not found at {db_path}")
