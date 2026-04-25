"""Party model — represents both Customers and Suppliers."""
from datetime import datetime
from ..extensions import db


class Party(db.Model):
    __tablename__ = 'parties'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False, index=True)  # customer / supplier / both
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    tax_number = db.Column(db.String(50), nullable=True)
    credit_limit = db.Column(db.Numeric(18, 2), default=0)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    woo_customer_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    invoices = db.relationship('Invoice', backref='party', lazy='dynamic',
                               foreign_keys='Invoice.party_id')

    @property
    def type_ar(self):
        mapping = {'customer': 'عميل', 'supplier': 'مورد', 'both': 'عميل ومورد'}
        return mapping.get(self.type, self.type)

    @property
    def balance(self):
        """Positive = owes us money (AR), Negative = we owe them (AP)."""
        total_invoiced = sum(
            float(inv.total) for inv in self.invoices.filter_by(type='sale')
            if inv.status not in ('draft', 'cancelled')
        )
        # Using vouchers instead of invoice.paid_amount
        total_receipts = sum(float(v.amount) for v in self.vouchers.filter_by(type='receipt'))
        
        # for suppliers
        total_purchases = sum(
            float(inv.total) for inv in self.invoices.filter_by(type='purchase')
            if inv.status not in ('draft', 'cancelled')
        )
        total_payments = sum(float(v.amount) for v in self.vouchers.filter_by(type='payment'))
        
        # customer balance = invoiced - receipts. supplier balance = purchases - payments
        if self.type == 'customer':
            return total_invoiced - total_receipts
        elif self.type == 'supplier':
            return total_purchases - total_payments
        else: # both
            return (total_invoiced - total_receipts) - (total_purchases - total_payments)

    @property
    def total_purchases(self):
        return sum(
            float(inv.total) for inv in self.invoices.filter_by(type='purchase')
            if inv.status not in ('draft', 'cancelled')
        )

    @property
    def display_name(self):
        return self.name_ar or self.name

    def __repr__(self):
        return f'<Party {self.type} {self.name}>'
