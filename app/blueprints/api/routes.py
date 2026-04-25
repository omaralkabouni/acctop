"""REST API routes — JSON endpoints for all modules."""
from flask import jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func

from . import api_bp
from ...extensions import db
from ...models.invoice import Invoice
from ...models.expense import Expense
from ...models.product import Product
from ...models.party import Party
from ...models.account import Account
from ...models.transaction import JournalEntry


def invoice_to_dict(inv):
    return {
        'id': inv.id, 'number': inv.number, 'status': inv.status,
        'status_ar': inv.status_ar, 'total': float(inv.total),
        'paid_amount': float(inv.paid_amount), 'balance_due': inv.balance_due,
        'date': str(inv.date), 'party_name': inv.party.display_name if inv.party else '',
    }


def product_to_dict(p):
    return {
        'id': p.id, 'sku': p.sku, 'name': p.name, 'name_ar': p.name_ar,
        'unit_price': float(p.unit_price), 'cost_price': float(p.cost_price),
        'stock_qty': float(p.stock_qty), 'unit': p.unit, 'is_low_stock': p.is_low_stock,
    }


def party_to_dict(p):
    return {
        'id': p.id, 'name': p.name, 'name_ar': p.name_ar,
        'type': p.type, 'type_ar': p.type_ar,
        'email': p.email, 'phone': p.phone, 'balance': p.balance,
    }


# --- Invoices ---
@api_bp.route('/invoices')
@login_required
def api_invoices():
    page = request.args.get('page', 1, type=int)
    invoices = Invoice.query.filter_by(type='sale').order_by(Invoice.date.desc()).paginate(page=page, per_page=50)
    return jsonify({
        'items': [invoice_to_dict(i) for i in invoices.items],
        'total': invoices.total, 'pages': invoices.pages, 'page': page,
    })


@api_bp.route('/invoices/<int:invoice_id>')
@login_required
def api_invoice_detail(invoice_id):
    inv = Invoice.query.get_or_404(invoice_id)
    data = invoice_to_dict(inv)
    data['lines'] = [
        {'description': l.description, 'qty': float(l.qty),
         'unit_price': float(l.unit_price), 'total': float(l.total)}
        for l in inv.lines
    ]
    return jsonify(data)


# --- Products ---
@api_bp.route('/products')
@login_required
def api_products():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return jsonify([product_to_dict(p) for p in products])


# --- Parties ---
@api_bp.route('/parties')
@login_required
def api_parties():
    party_type = request.args.get('type', '')
    q = Party.query.filter_by(is_active=True)
    if party_type:
        q = q.filter(Party.type.in_([party_type, 'both']))
    return jsonify([party_to_dict(p) for p in q.all()])


# --- Dashboard Stats ---
@api_bp.route('/stats/dashboard')
@login_required
def api_dashboard_stats():
    from datetime import date
    today = date.today()
    month_start = today.replace(day=1)

    revenue = db.session.query(func.coalesce(func.sum(Invoice.paid_amount), 0)).filter(
        Invoice.type == 'sale', Invoice.date >= month_start
    ).scalar() or 0

    expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.date >= month_start
    ).scalar() or 0

    outstanding = db.session.query(func.coalesce(func.sum(Invoice.total - Invoice.paid_amount), 0)).filter(
        Invoice.type == 'sale', Invoice.status.in_(['sent', 'partial', 'overdue'])
    ).scalar() or 0

    return jsonify({
        'revenue': float(revenue),
        'expenses': float(expenses),
        'net_profit': float(revenue) - float(expenses),
        'outstanding': float(outstanding),
        'currency': 'ر.س',
    })


# --- Accounts ---
@api_bp.route('/accounts')
@login_required
def api_accounts():
    accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    return jsonify([{
        'id': a.id, 'code': a.code, 'name_ar': a.name_ar,
        'type': a.type, 'type_ar': a.type_ar, 'balance': a.balance,
    } for a in accounts])
