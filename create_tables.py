from app import create_app
from app.extensions import db
from app.models.product import Product, ProductImage

app = create_app('development')
with app.app_context():
    db.create_all()
    print("Database tables created successfully (including product_images).")
