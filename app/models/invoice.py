"""Invoice and InvoiceLine models."""
from datetime import datetime
from ..extensions import db


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    type = db.Column(db.String(10), default='sale')   # sale / purchase
    party_id = db.Column(db.Integer, db.ForeignKey('parties.id'), nullable=True)
    manual_party_name = db.Column(db.String(200), nullable=True)
    manual_party_phone = db.Column(db.String(20), nullable=True)
    supplier_invoice_number = db.Column(db.String(50), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='draft')  # draft/sent/paid/partial/overdue/cancelled
    notes = db.Column(db.Text, nullable=True)

    subtotal = db.Column(db.Numeric(18, 2), default=0)
    discount_pct = db.Column(db.Numeric(5, 2), default=0)
    discount_amount = db.Column(db.Numeric(18, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=15)   # VAT %
    tax_amount = db.Column(db.Numeric(18, 2), default=0)
    total = db.Column(db.Numeric(18, 2), default=0)
    paid_amount = db.Column(db.Numeric(18, 2), default=0)

    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=True)
    woo_order_id = db.Column(db.Integer, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lines = db.relationship('InvoiceLine', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    journal_entry = db.relationship('JournalEntry', foreign_keys=[journal_entry_id])

    @property
    def balance_due(self):
        return float(self.total) - float(self.paid_amount)

    @property
    def status_ar(self):
        mapping = {
            'draft': 'مسودة',
            'sent': 'مُرسلة',
            'paid': 'مدفوعة',
            'partial': 'جزئي',
            'overdue': 'متأخرة',
            'cancelled': 'ملغاة',
        }
        return mapping.get(self.status, self.status)

    @property
    def party_display_name(self):
        if self.party:
            return self.party.display_name
        return self.manual_party_name or 'عميل نقدي'

    @property
    def type_ar(self):
        mapping = {'sale': 'مبيعات', 'purchase': 'مشتريات'}
        return mapping.get(self.type, self.type)

    @property
    def status_color(self):
        mapping = {
            'draft': 'gray',
            'sent': 'blue',
            'paid': 'green',
            'partial': 'yellow',
            'overdue': 'red',
            'cancelled': 'red',
        }
        return mapping.get(self.status, 'gray')

    def recalculate(self):
        """Recalculate totals from line items."""
        self.subtotal = sum(float(l.total) for l in self.lines)
        self.discount_amount = float(self.subtotal) * float(self.discount_pct) / 100
        taxable = float(self.subtotal) - float(self.discount_amount)
        self.tax_amount = taxable * float(self.tax_rate) / 100
        self.total = taxable + float(self.tax_amount)

    def __repr__(self):
        return f'<Invoice {self.number}>'


class InvoiceLine(db.Model):
    __tablename__ = 'invoice_lines'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    description = db.Column(db.String(255), nullable=False)
    qty = db.Column(db.Numeric(12, 3), default=1)
    unit_price = db.Column(db.Numeric(18, 2), default=0)
    discount_pct = db.Column(db.Numeric(5, 2), default=0)
    total = db.Column(db.Numeric(18, 2), default=0)

    product = db.relationship('Product', foreign_keys=[product_id])

    def recalculate(self):
        up = float(self.unit_price or 0)
        dp = float(self.discount_pct or 0)
        q = float(self.qty or 0)
        discounted = up * (1 - dp / 100)
        self.total = discounted * q

    def __repr__(self):
        return f'<InvoiceLine {self.description} x{self.qty}>'
