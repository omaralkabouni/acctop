import sqlite3
import os

db_path = 'instance/erp_top.db'
if not os.path.exists(db_path):
    # Try alternate path if running from root
    db_path = 'erp_top.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # 1. Get current schema for invoices
    cursor.execute("PRAGMA table_info(invoices)")
    columns = cursor.fetchall()
    
    # 2. Check if manual_party_name exists
    has_manual = any(col[1] == 'manual_party_name' for col in columns)
    
    # 3. Create temp table with NULLable party_id
    # We'll build the CREATE TABLE statement based on current columns but modify party_id
    
    # Actually, let's just define the new schema explicitly based on our model
    cursor.execute("""
    CREATE TABLE invoices_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number VARCHAR(30) NOT NULL UNIQUE,
        type VARCHAR(10),
        party_id INTEGER,
        manual_party_name VARCHAR(200),
        supplier_invoice_number VARCHAR(50),
        date DATE NOT NULL,
        due_date DATE,
        status VARCHAR(20),
        notes TEXT,
        subtotal NUMERIC(18, 2),
        discount_pct NUMERIC(5, 2),
        discount_amount NUMERIC(18, 2),
        tax_rate NUMERIC(5, 2),
        tax_amount NUMERIC(18, 2),
        total NUMERIC(18, 2),
        paid_amount NUMERIC(18, 2),
        journal_entry_id INTEGER,
        woo_order_id INTEGER,
        created_by INTEGER,
        created_at DATETIME,
        FOREIGN KEY(party_id) REFERENCES parties (id),
        FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id),
        FOREIGN KEY(created_by) REFERENCES users (id)
    )
    """)
    
    # 4. Copy data
    # We need to map old columns to new ones.
    # We'll fetch all data from old and insert into new.
    cursor.execute("SELECT * FROM invoices")
    rows = cursor.fetchall()
    
    # Get column names from old table to match indices
    old_col_names = [col[1] for col in columns]
    
    for row in rows:
        # Create a dict of values
        data = dict(zip(old_col_names, row))
        
        # Insert into new table
        # We need to be careful with column order. 
        # Since I defined invoices_new with specific order, I'll match it.
        cols_to_insert = [
            'id', 'number', 'type', 'party_id', 'manual_party_name', 'supplier_invoice_number',
            'date', 'due_date', 'status', 'notes', 'subtotal', 'discount_pct',
            'discount_amount', 'tax_rate', 'tax_amount', 'total', 'paid_amount',
            'journal_entry_id', 'woo_order_id', 'created_by', 'created_at'
        ]
        
        vals = []
        for c in cols_to_insert:
            vals.append(data.get(c))
            
        placeholders = ', '.join(['?' for _ in vals])
        cursor.execute(f"INSERT INTO invoices_new ({', '.join(cols_to_insert)}) VALUES ({placeholders})", vals)

    # 5. Swap tables
    cursor.execute("DROP TABLE invoices")
    cursor.execute("ALTER TABLE invoices_new RENAME TO invoices")
    
    conn.commit()
    print("Table 'invoices' recreated successfully with NULLable party_id.")

except Exception as e:
    conn.rollback()
    print(f"Error during migration: {e}")
finally:
    conn.close()
