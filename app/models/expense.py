"""Expense and ExpenseCategory models."""
from datetime import datetime
from ..extensions import db


class ExpenseCategory(db.Model):
    __tablename__ = 'expense_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    color = db.Column(db.String(10), default='#6b7280')
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)

    expenses = db.relationship('Expense', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'


class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    party_id = db.Column(db.Integer, db.ForeignKey('parties.id'), nullable=True)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    description = db.Column(db.String(300), nullable=False)
    receipt_url = db.Column(db.String(300), nullable=True)
    payment_method = db.Column(db.String(30), default='cash')  # cash/bank/credit
    is_paid = db.Column(db.Boolean, default=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship('Account', foreign_keys=[account_id])
    party = db.relationship('Party', foreign_keys=[party_id])

    @property
    def payment_method_ar(self):
        mapping = {'cash': 'نقداً', 'bank': 'تحويل بنكي', 'credit': 'آجل'}
        return mapping.get(self.payment_method, self.payment_method)

    def __repr__(self):
        return f'<Expense {self.description} {self.amount}>'
