from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        # Add manual_party_name
        db.session.execute(text("ALTER TABLE invoices ADD COLUMN manual_party_name VARCHAR(200)"))
        
        # Making a column nullable in SQLite is not directly supported via ALTER
        # But we can try to just use it if the DB allows it.
        # Actually, for SQLite, we usually have to recreate the table.
        # But let's see if we can just proceed.
        db.session.commit()
        print("Column 'manual_party_name' added.")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
