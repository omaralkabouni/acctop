from flask import render_template, request, jsonify, flash, url_for
from flask_login import login_required, current_user
from . import pos_bp
from ...extensions import db
from ...models.product import Product
from ...models.party import Party
from ...models.invoice import Invoice, InvoiceLine
from ...models.voucher import Voucher
from ...models.account import Account
from ...models.transaction import JournalEntry, JournalLine
from ...utils.decorators import permission_required
from datetime import datetime, date

@pos_bp.route('/')
@login_required
@permission_required('invoices')
def index():
    products = Product.query.filter_by(is_active=True).all()
    customers = Party.query.filter(Party.type.in_(['customer', 'both']), Party.is_active==True).all()
    accounts = Account.query.filter(Account.type == 'asset', Account.code.in_(['1110', '1111'])).all()
    return render_template('pos/index.html', title='نقطة البيع (POS)', 
                           products=products, customers=customers, accounts=accounts)

@pos_bp.route('/checkout', methods=['POST'])
@login_required
@permission_required('invoices')
def checkout():
    data = request.json
    if not data or not data.get('items'):
        return jsonify({'success': False, 'error': 'السلة فارغة'}), 400

    party_id = data.get('party_id')
    
    # Handle missing party_id for POS (default to Cash Customer)
    if not party_id:
        cash_party = Party.query.filter(Party.name.like('%نقدي%') | Party.name.like('%Cash%')).first()
        if cash_party:
            party_id = cash_party.id
        else:
            # Fallback if somehow not found
            return jsonify({'success': False, 'error': 'الرجاء اختيار عميل أو التأكد من وجود عميل نقدي في النظام'}), 400

    account_id = data.get('account_id')
    payment_method = data.get('payment_method', 'cash')
    total_amount = float(data.get('total', 0))
    paid_amount = float(data.get('paid', 0))
    
    # Determine Status
    if paid_amount <= 0:
        status = 'unpaid'
    elif paid_amount < total_amount:
        status = 'partial'
    else:
        status = 'paid'

    # 1. Create Invoice
    invoice = Invoice(
        number=f"POS-{datetime.now().strftime('%y%m%d%H%M%S')}",
        type='sale',
        party_id=party_id,
        date=date.today(),
        status=status,
        notes='بيع POS' + (' (آجل)' if data.get('is_credit') else ''),
        created_by=current_user.id,
        tax_rate=15.0 # Default
    )
    db.session.add(invoice)
    db.session.flush()

    # 2. Add Lines & Update Stock
    for item in data['items']:
        product = Product.query.get(item['id'])
        if not product: continue
        
        line = InvoiceLine(
            invoice_id=invoice.id,
            product_id=product.id,
            description=product.name_ar or product.name,
            qty=float(item['qty']),
            unit_price=float(item['price']),
            discount_pct=0
        )
        line.recalculate()
        db.session.add(line)
        
        # Simple stock reduction
        product.stock_qty = float(product.stock_qty) - float(item['qty'])

    invoice.recalculate()
    db.session.flush()

    # 3. Handle Payment (Voucher)
    if paid_amount > 0:
        voucher = Voucher(
            number=f"RV-POS-{invoice.id}",
            type='receipt',
            party_id=party_id,
            account_id=account_id or Account.query.filter_by(code='1110').first().id,
            amount=paid_amount,
            date=date.today(),
            notes=f'دفع فاتورة POS رقم {invoice.number}',
            created_by=current_user.id
        )
        db.session.add(voucher)
        invoice.paid_amount = paid_amount
        if invoice.paid_amount >= invoice.total:
            invoice.status = 'paid'
        else:
            invoice.status = 'partial'

    db.session.commit()
    
    return jsonify({
        'success': True, 
        'invoice_id': invoice.id,
        'print_url': url_for('invoices.view', invoice_id=invoice.id, print=1)
    })
