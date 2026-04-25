from app import create_app
from app.extensions import db
from app.models.party import Party

app = create_app()
with app.app_context():
    cash_party = Party.query.filter(Party.name.like('%نقدي%') | Party.name.like('%Cash%')).first()
    if cash_party:
        print(f"Found cash party: ID={cash_party.id}, Name={cash_party.name}")
    else:
        print("Cash party not found. Creating one...")
        cash_party = Party(
            name='Cash Customer',
            name_ar='عميل نقدي',
            type='customer',
            is_active=True
        )
        db.session.add(cash_party)
        db.session.commit()
        print(f"Created cash party: ID={cash_party.id}")
