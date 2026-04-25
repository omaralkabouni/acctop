from app import create_app
from app.extensions import db
from app.models.account import Account

app = create_app()
with app.app_context():
    if not Account.query.filter_by(code='1111').first():
        parent = Account.query.filter_by(code='1100').first()
        acc = Account(
            code='1111',
            name_ar='شام كاش',
            name_en='Sham Cash',
            type='asset',
            parent_id=parent.id if parent else None
        )
        db.session.add(acc)
        db.session.commit()
        print("Sham Cash account added successfully.")
    else:
        print("Sham Cash account already exists.")
