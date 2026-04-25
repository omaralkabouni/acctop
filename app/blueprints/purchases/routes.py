"""Purchases routes — similar to invoices but for type='purchase'."""
from datetime import date, datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from . import purchases_bp
from ...extensions import db
from ...models.invoice import Invoice, InvoiceLine
from ...models.party import Party
from ...models.product import Product, InventoryMovement
from ...models.transaction import JournalEntry, JournalLine
from ...models.account import Account
from ...utils.decorators import permission_required, role_required, log_action
from ...utils.helpers import generate_invoice_number, generate_journal_reference

def _create_purchase_journal(invoice):
    """Auto-create journal entry for a posted purchase invoice."""
    # AP Account (2110), Inventory Account (1130), Tax (2110 or separate)
    ap_acc = Account.query.filter_by(code='2110').first()  # AP
    inv_acc = Account.query.filter_by(code='1130').first() # Inventory
    tax_acc = Account.query.filter_by(code='2110').first() # Simplified tax
    
    if not ap_acc or not inv_acc:
        return None

    entry = JournalEntry(
        date=invoice.date,
        reference=generate_journal_reference(),
        description=f'فاتورة مشتريات رقم {invoice.number} - {invoice.party.display_name}',
        created_by=invoice.created_by,
        source='invoice', source_id=invoice.id
    )
    db.session.add(entry)
    db.session.flush()

    # Debit Inventory (Subtotal - Discount)
    taxable_amount = float(invoice.subtotal) - float(invoice.discount_amount)
    db.session.add(JournalLine(entry_id=entry.id, account_id=inv_acc.id, debit=taxable_amount, credit=0))
    
    # Debit Tax
    if float(invoice.tax_amount) > 0:
        db.session.add(JournalLine(entry_id=entry.id, account_id=tax_acc.id, debit=float(invoice.tax_amount), credit=0))
    
    # Credit AP (Total)
    db.session.add(JournalLine(entry_id=entry.id, account_id=ap_acc.id, debit=0, credit=float(invoice.total)))
    
    return entry

@purchases_bp.route('/')
@login_required
def index():
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    q = Invoice.query.filter_by(type='purchase')
    if search:
        q = q.join(Party).filter(
            Party.name.ilike(f'%{search}%') | 
            Invoice.number.ilike(f'%{search}%') |
            Invoice.supplier_invoice_number.ilike(f'%{search}%')
        )
    purchases = q.order_by(Invoice.id.desc()).paginate(page=page, per_page=20)
    return render_template('purchases/index.html', title='المشتريات', purchases=purchases, search=search)

@purchases_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('invoices') # Reusing invoice permission
def create():
    suppliers = Party.query.filter(Party.type.in_(['supplier', 'both']), Party.is_active == True).all()
    products = Product.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        party_id = request.form.get('party_id', type=int)
        inv_date_str = request.form.get('date')
        inv_date = datetime.strptime(inv_date_str, '%Y-%m-%d').date() if inv_date_str else date.today()
        
        invoice = Invoice(
            number=generate_invoice_number(prefix='PUR'),
            type='purchase',
            party_id=party_id,
            supplier_invoice_number=request.form.get('supplier_invoice_number'),
            date=inv_date,
            tax_rate=request.form.get('tax_rate', 15, type=float),
            discount_pct=request.form.get('discount_pct', 0, type=float),
            notes=request.form.get('notes', ''),
            status='draft',
            created_by=current_user.id,
        )
        db.session.add(invoice)
        db.session.flush()

        product_ids = request.form.getlist('product_id[]')
        descriptions = request.form.getlist('description[]')
        qtys = request.form.getlist('qty[]')
        prices = request.form.getlist('unit_price[]')

        for i, desc in enumerate(descriptions):
            if not desc.strip(): continue
            line = InvoiceLine(
                invoice_id=invoice.id,
                product_id=int(product_ids[i]) if product_ids[i] else None,
                description=desc.strip(),
                qty=float(qtys[i] or 1),
                unit_price=float(prices[i] or 0),
                discount_pct=0,
            )
            line.recalculate()
            db.session.add(line)

        db.session.flush()
        invoice.recalculate()

        action = request.form.get('action', 'save')
        if action == 'post':
            invoice.status = 'sent'
            entry = _create_purchase_journal(invoice)
            if entry: invoice.journal_entry_id = entry.id
            
            # Update Inventory (Stock IN)
            for line in invoice.lines:
                if line.product_id:
                    prod = Product.query.get(line.product_id)
                    prod.stock_qty = float(prod.stock_qty) + float(line.qty)
                    # Update cost price to latest purchase price
                    prod.cost_price = float(line.unit_price)
                    
                    db.session.add(InventoryMovement(
                        product_id=line.product_id, type='in', qty=line.qty,
                        unit_cost=line.unit_price, reference=invoice.number,
                        notes=f'مشتريات: {invoice.party.display_name}',
                        created_by=current_user.id
                    ))

        db.session.commit()
        flash(f'تم تسجيل فاتورة المشتريات {invoice.number} بنجاح', 'success')
        return redirect(url_for('purchases.index'))

    return render_template('purchases/form.html', title='فاتورة مشتريات جديدة', suppliers=suppliers, products=products)

@purchases_bp.route('/<int:purchase_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete(purchase_id):
    purchase = Invoice.query.filter_by(id=purchase_id, type='purchase').first_or_404()
    # If posted, we should ideally reverse inventory, but for simplicity we just delete if draft or warn
    if purchase.status != 'draft':
        # Simple reverse for now
        for line in purchase.lines:
            if line.product_id:
                prod = Product.query.get(line.product_id)
                prod.stock_qty = float(prod.stock_qty) - float(line.qty)
    
    db.session.delete(purchase)
    db.session.commit()
    flash('تم حذف الفاتورة بنجاح', 'success')
    return redirect(url_for('purchases.index'))
