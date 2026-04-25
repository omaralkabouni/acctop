"""Product and Inventory Movement models."""
from datetime import datetime
from ..extensions import db


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    unit_price = db.Column(db.Numeric(18, 2), default=0)
    cost_price = db.Column(db.Numeric(18, 2), default=0)
    stock_qty = db.Column(db.Numeric(12, 3), default=0)
    min_stock = db.Column(db.Numeric(12, 3), default=0)
    unit = db.Column(db.String(20), default='قطعة')
    is_active = db.Column(db.Boolean, default=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    woo_product_id = db.Column(db.Integer, nullable=True)
    image = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    movements = db.relationship('InventoryMovement', backref='product', lazy='dynamic')

    @property
    def is_low_stock(self):
        return float(self.stock_qty) <= float(self.min_stock)

    @property
    def stock_value(self):
        return float(self.stock_qty) * float(self.cost_price)

    def __repr__(self):
        return f'<Product {self.sku} {self.name}>'


class InventoryMovement(db.Model):
    __tablename__ = 'inventory_movements'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # in / out / adjustment
    qty = db.Column(db.Numeric(12, 3), nullable=False)
    unit_cost = db.Column(db.Numeric(18, 2), default=0)
    reference = db.Column(db.String(100), nullable=True)   # invoice number, etc.
    notes = db.Column(db.Text, nullable=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def type_ar(self):
        mapping = {'in': 'وارد', 'out': 'صادر', 'adjustment': 'تسوية'}
        return mapping.get(self.type, self.type)

    def __repr__(self):
        return f'<InventoryMovement {self.type} {self.qty}x product={self.product_id}>'
