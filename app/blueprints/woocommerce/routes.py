"""WooCommerce sync routes — connect, sync orders, customers, products."""
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user

from . import woo_bp
from ...extensions import db
from ...models.party import Party
from ...models.product import Product
from ...models.invoice import Invoice, InvoiceLine
from ...utils.decorators import role_required, log_action
from ...utils.helpers import generate_invoice_number
from datetime import datetime


def get_woo_api():
    """Return a WooCommerce API client if configured."""
    try:
        from woocommerce import API
        wcapi = API(
            url=current_app.config['WOO_URL'],
            consumer_key=current_app.config['WOO_CONSUMER_KEY'],
            consumer_secret=current_app.config['WOO_CONSUMER_SECRET'],
            version='wc/v3',
            timeout=30,
        )
        return wcapi
    except Exception as e:
        return None


@woo_bp.route('/')
@login_required
@role_required('admin', 'accountant')
def index():
    woo_url = current_app.config.get('WOO_URL', '')
    is_configured = bool(woo_url and woo_url != 'https://your-store.com')
    from ...models.invoice import Invoice
    synced_count = Invoice.query.filter(Invoice.woo_order_id.isnot(None)).count()
    return render_template('woocommerce/index.html', title='WooCommerce',
                           is_configured=is_configured, woo_url=woo_url,
                           synced_count=synced_count)


@woo_bp.route('/test-connection')
@login_required
@role_required('admin')
def test_connection():
    wcapi = get_woo_api()
    if not wcapi:
        return jsonify({'status': 'error', 'message': 'WooCommerce غير مُهيأ'})
    try:
        r = wcapi.get('orders', params={'per_page': 1})
        if r.status_code == 200:
            return jsonify({'status': 'ok', 'message': 'الاتصال ناجح ✅'})
        else:
            return jsonify({'status': 'error', 'message': f'خطأ HTTP {r.status_code}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@woo_bp.route('/sync-orders', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def sync_orders():
    wcapi = get_woo_api()
    if not wcapi:
        flash('WooCommerce غير مُهيأ. يرجى تحديث ملف .env', 'error')
        return redirect(url_for('woocommerce.index'))

    try:
        page = 1
        synced = 0
        skipped = 0

        while True:
            r = wcapi.get('orders', params={'per_page': 50, 'page': page, 'status': 'completed'})
            orders = r.json()
            if not orders:
                break

            for order in orders:
                woo_id = order['id']
                if Invoice.query.filter_by(woo_order_id=woo_id).first():
                    skipped += 1
                    continue

                # Find or create customer
                billing = order.get('billing', {})
                customer_name = f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip() or 'WooCommerce Customer'
                customer_email = billing.get('email', '')

                party = Party.query.filter_by(email=customer_email).first() if customer_email else None
                if not party:
                    party = Party(
                        type='customer', name=customer_name,
                        email=customer_email,
                        phone=billing.get('phone', ''),
                        address=f"{billing.get('address_1', '')} {billing.get('city', '')}".strip(),
                    )
                    db.session.add(party)
                    db.session.flush()

                # Create invoice
                order_date = order.get('date_created', '')[:10] if order.get('date_created') else datetime.utcnow().date()
                invoice = Invoice(
                    number=generate_invoice_number('WOO'),
                    type='sale',
                    party_id=party.id,
                    date=order_date,
                    status='paid' if order['payment_method'] else 'sent',
                    tax_rate=0,
                    discount_pct=0,
                    total=float(order['total']),
                    subtotal=float(order['subtotal']),
                    paid_amount=float(order['total']) if order.get('date_paid') else 0,
                    woo_order_id=woo_id,
                    created_by=current_user.id,
                    notes=f"WooCommerce Order #{woo_id}",
                )
                db.session.add(invoice)
                db.session.flush()

                for item in order.get('line_items', []):
                    line = InvoiceLine(
                        invoice_id=invoice.id,
                        description=item.get('name', 'منتج'),
                        qty=float(item.get('quantity', 1)),
                        unit_price=float(item.get('price', 0)),
                        total=float(item.get('total', 0)),
                    )
                    db.session.add(line)

                synced += 1

            if len(orders) < 50:
                break
            page += 1

        db.session.commit()
        log_action(current_user.id, 'create', 'WooSync', 0,
                   new_values={'synced': synced, 'skipped': skipped})
        flash(f'تمت المزامنة: {synced} طلب جديد، {skipped} طلب موجود مسبقاً', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في المزامنة: {str(e)}', 'error')

    return redirect(url_for('woocommerce.index'))


@woo_bp.route('/sync-products', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def sync_products():
    wcapi = get_woo_api()
    if not wcapi:
        flash('WooCommerce غير مُهيأ', 'error')
        return redirect(url_for('woocommerce.index'))

    try:
        r = wcapi.get('products', params={'per_page': 100})
        products = r.json()
        synced = 0
        for p_data in products:
            woo_id = p_data['id']
            product = Product.query.filter_by(woo_product_id=woo_id).first()
            if not product:
                product = Product(
                    name=p_data.get('name', ''),
                    sku=p_data.get('sku') or None,
                    unit_price=float(p_data.get('price', 0) or 0),
                    cost_price=float(p_data.get('regular_price', 0) or 0),
                    stock_qty=float(p_data.get('stock_quantity', 0) or 0),
                    woo_product_id=woo_id,
                )
                db.session.add(product)
                synced += 1

        db.session.commit()
        flash(f'تمت مزامنة {synced} منتج جديد', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {str(e)}', 'error')

    return redirect(url_for('woocommerce.index'))
