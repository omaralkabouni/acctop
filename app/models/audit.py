"""Audit Log model for financial action tracking."""
from datetime import datetime
from ..extensions import db
import json


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)   # create/update/delete
    entity = db.Column(db.String(50), nullable=False)   # Invoice/Expense/etc.
    entity_id = db.Column(db.Integer, nullable=True)
    old_values = db.Column(db.Text, nullable=True)
    new_values = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @property
    def old_values_dict(self):
        try:
            return json.loads(self.old_values) if self.old_values else {}
        except Exception:
            return {}

    @property
    def new_values_dict(self):
        try:
            return json.loads(self.new_values) if self.new_values else {}
        except Exception:
            return {}

    @property
    def action_ar(self):
        mapping = {'create': 'إنشاء', 'update': 'تحديث', 'delete': 'حذف', 'login': 'دخول', 'logout': 'خروج'}
        return mapping.get(self.action, self.action)

    def __repr__(self):
        return f'<AuditLog {self.action} {self.entity}#{self.entity_id}>'
