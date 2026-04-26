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
        selling_prices = request.form.getlist('selling_price[]')

        for i, desc in enumerate(descriptions):
            if not desc.strip(): continue
            p_id = int(product_ids[i]) if i < len(product_ids) and product_ids[i] else None
            line = InvoiceLine(
                invoice_id=invoice.id,
                product_id=p_id,
                description=desc.strip(),
                qty=float(qtys[i] or 1),
                unit_price=float(prices[i] or 0),
                discount_pct=0,
            )
            line.recalculate()
            db.session.add(line)
            
            # Update selling price of the product if provided
            if p_id and i < len(selling_prices) and selling_prices[i]:
                prod = Product.query.get(p_id)
                if prod:
                    prod.unit_price = float(selling_prices[i])

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


@purchases_bp.route('/<int:purchase_id>')
@login_required
def view(purchase_id):
    purchase = Invoice.query.filter_by(id=purchase_id, type='purchase').first_or_404()
    return render_template('purchases/view.html', title=f'فاتورة مشتريات {purchase.number}', purchase=purchase)


@purchases_bp.route('/<int:purchase_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('invoices')
def edit(purchase_id):
    purchase = Invoice.query.filter_by(id=purchase_id, type='purchase').first_or_404()
    
    # Allow editing even if sent, but handle reversal
    suppliers = Party.query.filter(Party.type.in_(['supplier', 'both']), Party.is_active == True).all()
    products = Product.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        # If it was sent, we need to REVERSE the impact before deleting old lines
        if purchase.status != 'draft':
            for line in purchase.lines:
                if line.product_id:
                    prod = Product.query.get(line.product_id)
                    # For purchase, we subtract what we added
                    prod.stock_qty = float(prod.stock_qty) - float(line.qty)
            
            # Delete associated movements and journal
            InventoryMovement.query.filter_by(reference=purchase.number).delete()
            if purchase.journal_entry_id:
                JournalLine.query.filter_by(entry_id=purchase.journal_entry_id).delete()
                JournalEntry.query.filter_by(id=purchase.journal_entry_id).delete()
                purchase.journal_entry_id = None
            
            purchase.status = 'draft' # Reset to draft after editing a sent one

        purchase.party_id = request.form.get('party_id', type=int)
        inv_date_str = request.form.get('date')
        if inv_date_str:
            purchase.date = datetime.strptime(inv_date_str, '%Y-%m-%d').date()
        purchase.supplier_invoice_number = request.form.get('supplier_invoice_number')
        purchase.tax_rate = request.form.get('tax_rate', 15, type=float)
        purchase.discount_pct = request.form.get('discount_pct', 0, type=float)
        purchase.notes = request.form.get('notes', '')

        # Delete existing lines
        InvoiceLine.query.filter_by(invoice_id=purchase.id).delete()

        product_ids = request.form.getlist('product_id[]')
        descriptions = request.form.getlist('description[]')
        qtys = request.form.getlist('qty[]')
        prices = request.form.getlist('unit_price[]')
        selling_prices = request.form.getlist('selling_price[]')

        for i, desc in enumerate(descriptions):
            if not desc.strip(): continue
            p_id = int(product_ids[i]) if i < len(product_ids) and product_ids[i] else None
            line = InvoiceLine(
                invoice_id=purchase.id,
                product_id=p_id,
                description=desc.strip(),
                qty=float(qtys[i] or 1),
                unit_price=float(prices[i] or 0),
                discount_pct=0,
            )
            line.recalculate()
            db.session.add(line)
            
            # Update selling price of the product if provided
            if p_id and i < len(selling_prices) and selling_prices[i]:
                prod = Product.query.get(p_id)
                if prod:
                    prod.unit_price = float(selling_prices[i])

        db.session.flush()
        purchase.recalculate()
        db.session.commit()
        flash('تم تحديث الفاتورة بنجاح وإعادتها لحالة المسودة للمراجعة', 'info')
        return redirect(url_for('purchases.view', purchase_id=purchase.id))

    return render_template('purchases/form.html', title='تعديل فاتورة مشتريات',
                           purchase=purchase, suppliers=suppliers, products=products)


@purchases_bp.route('/<int:purchase_id>/post', methods=['POST'])
@login_required
@permission_required('invoices')
def post_purchase(purchase_id):
    purchase = Invoice.query.filter_by(id=purchase_id, type='purchase').first_or_404()
    if purchase.status != 'draft':
        flash('الفاتورة معتمدة مسبقاً', 'error')
        return redirect(url_for('purchases.view', purchase_id=purchase_id))

    purchase.status = 'sent'
    entry = _create_purchase_journal(purchase)
    if entry:
        purchase.journal_entry_id = entry.id
        
    # Update Inventory (Stock IN)
    for line in purchase.lines:
        if line.product_id:
            prod = Product.query.get(line.product_id)
            prod.stock_qty = float(prod.stock_qty) + float(line.qty)
            prod.cost_price = float(line.unit_price) # Update cost to latest purchase price
            
            db.session.add(InventoryMovement(
                product_id=line.product_id, type='in', qty=line.qty,
                unit_cost=line.unit_price, reference=purchase.number,
                notes=f'مشتريات: {purchase.party.display_name}',
                created_by=current_user.id
            ))

    db.session.commit()
    flash('تم اعتماد الفاتورة وتحديث المخزون', 'success')
    return redirect(url_for('purchases.view', purchase_id=purchase_id))


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
