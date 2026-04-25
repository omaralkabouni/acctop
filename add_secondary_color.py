from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE system_settings ADD COLUMN secondary_color VARCHAR(10) DEFAULT '#006c49'"))
            conn.commit()
            print("Successfully added secondary_color column.")
        except Exception as e:
            print(f"Error: {e}")
