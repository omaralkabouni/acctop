from datetime import date, datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from . import quotations_bp
from ...extensions import db
from ...models.invoice import Invoice, InvoiceLine
from ...models.party import Party
from ...models.product import Product
from ...utils.decorators import permission_required, role_required, log_action
from ...utils.helpers import generate_invoice_number

@quotations_bp.route('/')
@login_required
def index():
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    q = Invoice.query.filter_by(type='quotation')
    if search:
        q = q.join(Party).filter(
            Party.name.ilike(f'%{search}%') | Invoice.number.ilike(f'%{search}%')
        )
    quotations = q.order_by(Invoice.id.desc()).paginate(page=page, per_page=20)
    return render_template('quotations/index.html', title='عروض الأسعار', quotations=quotations, search=search)

@quotations_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('invoices')
def create():
    customers = Party.query.filter(Party.type.in_(['customer', 'both']), Party.is_active == True).all()
    products = Product.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        party_id = request.form.get('party_id', type=int) if request.form.get('party_id') else None
        manual_name = request.form.get('manual_party_name')
        manual_phone = request.form.get('manual_party_phone')
        
        quote = Invoice(
            number=request.form.get('number') or f"QT-{datetime.now().strftime('%y%m%d%H%M%S')}",
            type='quotation',
            party_id=party_id,
            manual_party_name=manual_name,
            manual_party_phone=manual_phone,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date() if request.form.get('date') else date.today(),
            due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date() if request.form.get('due_date') else None,
            tax_rate=request.form.get('tax_rate', 15, type=float),
            discount_pct=request.form.get('discount_pct', 0, type=float),
            notes=request.form.get('notes', ''),
            status='draft',
            created_by=current_user.id,
        )
        db.session.add(quote)
        db.session.flush()

        product_ids = request.form.getlist('product_id[]')
        descriptions = request.form.getlist('description[]')
        qtys = request.form.getlist('qty[]')
        prices = request.form.getlist('unit_price[]')
        discounts = request.form.getlist('line_discount[]')

        for i, desc in enumerate(descriptions):
            if not desc.strip(): continue
            line = InvoiceLine(
                invoice_id=quote.id,
                product_id=int(product_ids[i]) if product_ids[i] else None,
                description=desc.strip(),
                qty=float(qtys[i] or 1),
                unit_price=float(prices[i] or 0),
                discount_pct=float(discounts[i] or 0)
            )
            line.recalculate()
            db.session.add(line)

        db.session.flush()
        quote.recalculate()
        db.session.commit()
        flash(f'تم إنشاء عرض السعر {quote.number} بنجاح', 'success')
        return redirect(url_for('quotations.index'))

    return render_template('quotations/form.html', title='عرض سعر جديد', customers=customers, products=products)

@quotations_bp.route('/edit/<int:quote_id>', methods=['GET', 'POST'])
@login_required
@permission_required('invoices')
def edit(quote_id):
    quote = Invoice.query.filter_by(id=quote_id, type='quotation').first_or_404()
    customers = Party.query.filter(Party.type.in_(['customer', 'both']), Party.is_active == True).all()
    products = Product.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        quote.party_id = request.form.get('party_id', type=int) if request.form.get('party_id') else None
        quote.manual_party_name = request.form.get('manual_party_name')
        quote.manual_party_phone = request.form.get('manual_party_phone')
        quote.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date() if request.form.get('date') else date.today()
        quote.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date() if request.form.get('due_date') else None
        quote.tax_rate = request.form.get('tax_rate', 15, type=float)
        quote.discount_pct = request.form.get('discount_pct', 0, type=float)
        quote.notes = request.form.get('notes', '')
        
        # Refresh lines
        InvoiceLine.query.filter_by(invoice_id=quote.id).delete()
        
        product_ids = request.form.getlist('product_id[]')
        descriptions = request.form.getlist('description[]')
        qtys = request.form.getlist('qty[]')
        prices = request.form.getlist('unit_price[]')
        discounts = request.form.getlist('line_discount[]')

        for i, desc in enumerate(descriptions):
            if not desc.strip(): continue
            line = InvoiceLine(
                invoice_id=quote.id,
                product_id=int(product_ids[i]) if product_ids[i] else None,
                description=desc.strip(),
                qty=float(qtys[i] or 1),
                unit_price=float(prices[i] or 0),
                discount_pct=float(discounts[i] or 0)
            )
            line.recalculate()
            db.session.add(line)

        db.session.flush()
        quote.recalculate()
        db.session.commit()
        flash(f'تم تحديث عرض السعر {quote.number} بنجاح', 'success')
        return redirect(url_for('quotations.index'))

    return render_template('quotations/form.html', title='تعديل عرض سعر', customers=customers, products=products, quote=quote)


@quotations_bp.route('/convert/<int:quote_id>')
@login_required
@permission_required('invoices')
def convert(quote_id):
    quote = Invoice.query.filter_by(id=quote_id, type='quotation').first_or_404()
    
    # Auto-create customer if manual
    target_party_id = quote.party_id
    if not target_party_id and quote.manual_party_name:
        new_customer = Party(
            name=quote.manual_party_name,
            phone=quote.manual_party_phone,
            type='customer',
            is_active=True
        )
        db.session.add(new_customer)
        db.session.flush()
        target_party_id = new_customer.id

    # Create new Invoice from Quotation
    new_inv = Invoice(
        number=generate_invoice_number(prefix='INV'),
        type='sale',
        party_id=target_party_id,
        manual_party_name=quote.manual_party_name if not target_party_id else None,
        manual_party_phone=quote.manual_party_phone if not target_party_id else None,
        date=date.today(),
        tax_rate=quote.tax_rate,
        discount_pct=quote.discount_pct,
        notes=f"مُحول من عرض سعر رقم {quote.number}\n{quote.notes}",
        status='draft',
        created_by=current_user.id
    )
    db.session.add(new_inv)
    db.session.flush()

    for ql in quote.lines:
        il = InvoiceLine(
            invoice_id=new_inv.id,
            product_id=ql.product_id,
            description=ql.description,
            qty=ql.qty,
            unit_price=ql.unit_price,
            discount_pct=ql.discount_pct
        )
        il.recalculate()
        db.session.add(il)

    db.session.flush()
    new_inv.recalculate()
    
    quote.status = 'converted' # Mark as converted
    db.session.commit()
    
    flash(f'تم تحويل عرض السعر إلى فاتورة مبيعات رقم {new_inv.number}', 'success')
    return redirect(url_for('invoices.view', invoice_id=new_inv.id))

@quotations_bp.route('/delete/<int:quote_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete(quote_id):
    quote = Invoice.query.filter_by(id=quote_id, type='quotation').first_or_404()
    db.session.delete(quote)
    db.session.commit()
    flash('تم حذف عرض السعر بنجاح', 'success')
    return redirect(url_for('quotations.index'))
