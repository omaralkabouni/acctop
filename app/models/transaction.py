"""Journal Entries and Journal Lines (double-entry bookkeeping)."""
from datetime import datetime
from ..extensions import db


class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    reference = db.Column(db.String(50), nullable=True, index=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='posted')  # draft / posted / reversed
    source = db.Column(db.String(50), nullable=True)     # manual / invoice / expense / woo
    source_id = db.Column(db.Integer, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lines = db.relationship('JournalLine', backref='entry', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def total_debit(self):
        return sum(line.debit for line in self.lines)

    @property
    def total_credit(self):
        return sum(line.credit for line in self.lines)

    @property
    def is_balanced(self):
        return abs(self.total_debit - self.total_credit) < 0.001

    def __repr__(self):
        return f'<JournalEntry #{self.id} {self.reference}>'


class JournalLine(db.Model):
    __tablename__ = 'journal_lines'

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    debit = db.Column(db.Numeric(18, 2), default=0)
    credit = db.Column(db.Numeric(18, 2), default=0)
    description = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<JournalLine entry={self.entry_id} D={self.debit} C={self.credit}>'
