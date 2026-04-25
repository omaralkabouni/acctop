"""
ERP TOP - Main entry point
Run with: python run.py  OR  flask run
"""
from app import create_app, db
from app.models.user import User, Role
from app.models.account import Account
from app.models.expense import ExpenseCategory

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return dict(app=app, db=db, User=User, Role=Role)


@app.cli.command("init-db")
def init_db():
    """Initialize the database with seed data."""
    with app.app_context():
        db.create_all()
        seed_data()
        print("Database initialized successfully.")


def seed_data():
    """Seed initial roles, admin user, and chart of accounts."""
    from werkzeug.security import generate_password_hash

    # --- Roles ---
    roles = [
        Role(name='admin', name_ar='مدير النظام', permissions='all'),
        Role(name='accountant', name_ar='محاسب', permissions='accounts,invoices,reports,expenses,inventory,parties'),
        Role(name='employee', name_ar='موظف', permissions='invoices,expenses'),
    ]
    for role in roles:
        if not Role.query.filter_by(name=role.name).first():
            db.session.add(role)
    db.session.commit()

    # --- Admin User ---
    admin_role = Role.query.filter_by(name='admin').first()
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@erptop.com',
            full_name='مدير النظام',
            role_id=admin_role.id,
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("  -> Admin user created: admin / admin123")

    # --- Chart of Accounts ---
    accounts_seed = [
        # Assets
        {'code': '1000', 'name_ar': 'الأصول', 'name_en': 'Assets', 'type': 'asset', 'parent_code': None},
        {'code': '1100', 'name_ar': 'الأصول المتداولة', 'name_en': 'Current Assets', 'type': 'asset', 'parent_code': '1000'},
        {'code': '1110', 'name_ar': 'النقدية والبنوك', 'name_en': 'Cash & Banks', 'type': 'asset', 'parent_code': '1100'},
        {'code': '1111', 'name_ar': 'شام كاش', 'name_en': 'Sham Cash', 'type': 'asset', 'parent_code': '1100'},
        {'code': '1120', 'name_ar': 'الذمم المدينة', 'name_en': 'Accounts Receivable', 'type': 'asset', 'parent_code': '1100'},
        {'code': '1130', 'name_ar': 'المخزون', 'name_en': 'Inventory', 'type': 'asset', 'parent_code': '1100'},
        {'code': '1200', 'name_ar': 'الأصول الثابتة', 'name_en': 'Fixed Assets', 'type': 'asset', 'parent_code': '1000'},
        # Liabilities
        {'code': '2000', 'name_ar': 'الخصوم', 'name_en': 'Liabilities', 'type': 'liability', 'parent_code': None},
        {'code': '2100', 'name_ar': 'الخصوم المتداولة', 'name_en': 'Current Liabilities', 'type': 'liability', 'parent_code': '2000'},
        {'code': '2110', 'name_ar': 'الذمم الدائنة', 'name_en': 'Accounts Payable', 'type': 'liability', 'parent_code': '2100'},
        {'code': '2120', 'name_ar': 'القروض قصيرة الأجل', 'name_en': 'Short-term Loans', 'type': 'liability', 'parent_code': '2100'},
        # Equity
        {'code': '3000', 'name_ar': 'حقوق الملكية', 'name_en': 'Equity', 'type': 'equity', 'parent_code': None},
        {'code': '3100', 'name_ar': 'رأس المال', 'name_en': 'Capital', 'type': 'equity', 'parent_code': '3000'},
        {'code': '3200', 'name_ar': 'الأرباح المحتجزة', 'name_en': 'Retained Earnings', 'type': 'equity', 'parent_code': '3000'},
        # Revenue
        {'code': '4000', 'name_ar': 'الإيرادات', 'name_en': 'Revenue', 'type': 'revenue', 'parent_code': None},
        {'code': '4100', 'name_ar': 'إيرادات المبيعات', 'name_en': 'Sales Revenue', 'type': 'revenue', 'parent_code': '4000'},
        {'code': '4200', 'name_ar': 'إيرادات الخدمات', 'name_en': 'Service Revenue', 'type': 'revenue', 'parent_code': '4000'},
        # Expenses
        {'code': '5000', 'name_ar': 'المصروفات', 'name_en': 'Expenses', 'type': 'expense', 'parent_code': None},
        {'code': '5100', 'name_ar': 'تكلفة المبيعات', 'name_en': 'Cost of Goods Sold', 'type': 'expense', 'parent_code': '5000'},
        {'code': '5200', 'name_ar': 'مصروفات إدارية', 'name_en': 'Administrative Expenses', 'type': 'expense', 'parent_code': '5000'},
        {'code': '5300', 'name_ar': 'مصروفات تشغيلية', 'name_en': 'Operating Expenses', 'type': 'expense', 'parent_code': '5000'},
        {'code': '5400', 'name_ar': 'مصروفات التسويق', 'name_en': 'Marketing Expenses', 'type': 'expense', 'parent_code': '5000'},
    ]

    code_to_id = {}
    for acc_data in accounts_seed:
        if not Account.query.filter_by(code=acc_data['code']).first():
            parent_id = None
            if acc_data['parent_code']:
                parent_id = code_to_id.get(acc_data['parent_code'])
            acc = Account(
                code=acc_data['code'],
                name_ar=acc_data['name_ar'],
                name_en=acc_data['name_en'],
                type=acc_data['type'],
                parent_id=parent_id
            )
            db.session.add(acc)
            db.session.flush()
            code_to_id[acc_data['code']] = acc.id
        else:
            existing = Account.query.filter_by(code=acc_data['code']).first()
            code_to_id[acc_data['code']] = existing.id
    db.session.commit()
    print("  -> Chart of accounts seeded")

    # --- Expense Categories ---
    categories = [
        ExpenseCategory(name='رواتب وأجور', color='#10b981'),
        ExpenseCategory(name='إيجارات', color='#3b82f6'),
        ExpenseCategory(name='مرافق', color='#f59e0b'),
        ExpenseCategory(name='سفر وتنقل', color='#8b5cf6'),
        ExpenseCategory(name='اتصالات', color='#06b6d4'),
        ExpenseCategory(name='صيانة', color='#f97316'),
        ExpenseCategory(name='أخرى', color='#6b7280'),
    ]
    for cat in categories:
        if not ExpenseCategory.query.filter_by(name=cat.name).first():
            db.session.add(cat)
    db.session.commit()
    print("  -> Expense categories seeded")

    # --- System Settings ---
    from app.models.settings import SystemSettings
    if not SystemSettings.query.first():
        settings = SystemSettings(
            company_name='ERP TOP',
            tax_rate=15.0,
            currency_symbol='ر.س',
            exchange_rate=1.0
        )
        db.session.add(settings)
        db.session.commit()
        print("  -> Initial system settings created")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5566)
