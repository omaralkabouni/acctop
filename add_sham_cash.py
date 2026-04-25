from app import create_app, db
from app.models.account import Account

app = create_app()
with app.app_context():
    # Find parent 'Cash & Banks' (1110)
    parent = Account.query.filter_by(code='1110').first()
    if not parent:
        # Create it if missing
        parent = Account(code='1110', name_ar='النقدية والبنوك', name_en='Cash & Banks', type='asset')
        db.session.add(parent)
        db.session.flush()

    # Add Sham Cash
    sham_cash = Account.query.filter_by(name_ar='الشام كاش').first()
    if not sham_cash:
        sham_cash = Account(
            code='1111', 
            name_ar='الشام كاش', 
            name_en='Sham Cash', 
            type='asset',
            parent_id=parent.id
        )
        db.session.add(sham_cash)
        db.session.commit()
        print("Sham Cash account created successfully.")
    else:
        print("Sham Cash account already exists.")
