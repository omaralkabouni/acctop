"""Chart of Accounts model."""
from ..extensions import db


ACCOUNT_TYPES = {
    'asset': 'أصول',
    'liability': 'خصوم',
    'equity': 'حقوق ملكية',
    'revenue': 'إيرادات',
    'expense': 'مصروفات',
}


class Account(db.Model):
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name_ar = db.Column(db.String(150), nullable=False)
    name_en = db.Column(db.String(150), nullable=False, default='')
    type = db.Column(db.String(20), nullable=False)   # asset/liability/equity/revenue/expense
    parent_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    # Self-referential relationship
    children = db.relationship('Account', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    # Journal lines
    journal_lines = db.relationship('JournalLine', backref='account', lazy='dynamic')

    @property
    def type_ar(self):
        return ACCOUNT_TYPES.get(self.type, self.type)

    @property
    def balance(self):
        """Net balance: sum(debit) - sum(credit) for assets/expenses, else reversed."""
        from .transaction import JournalLine
        total_debit = db.session.query(
            db.func.coalesce(db.func.sum(JournalLine.debit), 0)
        ).filter(JournalLine.account_id == self.id).scalar()
        total_credit = db.session.query(
            db.func.coalesce(db.func.sum(JournalLine.credit), 0)
        ).filter(JournalLine.account_id == self.id).scalar()

        if self.type in ('asset', 'expense'):
            return total_debit - total_credit
        else:
            return total_credit - total_debit

    @property
    def total_debit(self):
        from .transaction import JournalLine
        return db.session.query(
            db.func.coalesce(db.func.sum(JournalLine.debit), 0)
        ).filter(JournalLine.account_id == self.id).scalar()

    @property
    def total_credit(self):
        from .transaction import JournalLine
        return db.session.query(
            db.func.coalesce(db.func.sum(JournalLine.credit), 0)
        ).filter(JournalLine.account_id == self.id).scalar()

    def __repr__(self):
        return f'<Account {self.code} {self.name_ar}>'
