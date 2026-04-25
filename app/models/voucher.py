"""Voucher model — Receipt and Payment Vouchers."""
from datetime import datetime
from ..extensions import db


class Voucher(db.Model):
    __tablename__ = 'vouchers'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), nullable=False, unique=True, index=True)
    type = db.Column(db.String(20), nullable=False, index=True)  # 'receipt' (سند قبض) / 'payment' (سند صرف)
    party_id = db.Column(db.Integer, db.ForeignKey('parties.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)  # Bank or Cash
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Financial linkages
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=True)
    
    # Audit
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    party = db.relationship('Party', backref=db.backref('vouchers', lazy='dynamic'))
    account = db.relationship('Account')
    journal_entry = db.relationship('JournalEntry')
    creator = db.relationship('User')

    @property
    def type_ar(self):
        return 'سند قبض' if self.type == 'receipt' else 'سند صرف'

    def __repr__(self):
        return f'<Voucher {self.number} ({self.type}) Party={self.party_id} Amount={self.amount}>'
