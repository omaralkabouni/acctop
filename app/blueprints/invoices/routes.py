"""Invoices routes — full CRUD with line items, payments, and accounting entries."""
from datetime import date, datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from . import invoices_bp
from ...extensions import db
from ...models.invoice import Invoice, InvoiceLine
from ...models.party import Party
from ...models.product import Product, InventoryMovement
from ...models.transaction import JournalEntry, JournalLine
from ...models.account import Account
from ...utils.decorators import permission_required, role_required, log_action
from ...utils.helpers import generate_invoice_number, generate_journal_reference


def _create_invoice_journal(invoice):
    """Auto-create journal entry for a posted invoice."""
    ar_acc = Account.query.filter_by(code='1120').first()  # AR
    rev_acc = Account.query.filter_by(code='4100').first()  # Sales Revenue
    tax_acc = Account.query.filter_by(code='2110').first()  # Tax payable (simplified)

    if not ar_acc or not rev_acc:
        return None

    entry = JournalEntry(
        date=invoice.date,
        reference=generate_journal_reference(),
        description=f'فاتورة مبيعات رقم {invoice.number} - {invoice.party.display_name}',
        created_by=invoice.created_by,
        source='invoice',
        source_id=invoice.id,
    )
    db.session.add(entry)
    db.session.flush()

    # Debit AR
    db.session.add(JournalLine(entry_id=entry.id, account_id=ar_acc.id,
                                debit=float(invoice.total), credit=0))
    # Credit Revenue
    db.session.add(JournalLine(entry_id=entry.id, account_id=rev_acc.id,
                                debit=0, credit=float(invoice.subtotal) - float(invoice.discount_amount)))
    # Credit Tax (if any)
    if float(invoice.tax_amount) > 0 and tax_acc:
        db.session.add(JournalLine(entry_id=entry.id, account_id=tax_acc.id,
                                    debit=0, credit=float(invoice.tax_amount)))
    return entry


@invoices_bp.route('/')
@login_required
def index():
    status_filter = request.args.get('status', '')
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    q = Invoice.query.filter_by(type='sale')
    if status_filter:
        q = q.filter_by(status=status_filter)
    if search:
        q = q.join(Party).filter(
            Party.name.ilike(f'%{search}%') | Invoice.number.ilike(f'%{search}%')
        )
    invoices = q.order_by(Invoice.id.desc()).paginate(page=page, per_page=20)
    return render_template('invoices/index.html', title='الفواتير', invoices=invoices,
                           status_filter=status_filter, search=search)


@invoices_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('invoices')
def create():
    customers = Party.query.filter(Party.type.in_(['customer', 'both']), Party.is_active == True).all()
    products = Product.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        party_id = request.form.get('party_id', type=int)
        if not party_id:
            flash('الرجاء اختيار العميل بشكل صحيح من القائمة', 'error')
            return redirect(url_for('invoices.create'))
        inv_date_str = request.form.get('date')
        inv_date = datetime.strptime(inv_date_str, '%Y-%m-%d').date() if inv_date_str else date.today()
        due_date_str = request.form.get('due_date')
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        tax_rate = request.form.get('tax_rate', 15, type=float)
        discount_pct = request.form.get('discount_pct', 0, type=float)
        notes = request.form.get('notes', '')

        invoice = Invoice(
            number=generate_invoice_number(),
            type='sale',
            party_id=party_id,
            date=inv_date,
            due_date=due_date,
            tax_rate=tax_rate,
            discount_pct=discount_pct,
            notes=notes,
            status='draft',
            created_by=current_user.id,
        )
        db.session.add(invoice)
        db.session.flush()

        product_ids = request.form.getlist('product_id[]')
        descriptions = request.form.getlist('description[]')
        qtys = request.form.getlist('qty[]')
        prices = request.form.getlist('unit_price[]')
        line_discounts = request.form.getlist('line_discount[]')

        for i, desc in enumerate(descriptions):
            if not desc.strip():
                continue
            line = InvoiceLine(
                invoice_id=invoice.id,
                product_id=int(product_ids[i]) if product_ids[i] else None,
                description=desc.strip(),
                qty=float(qtys[i] or 1),
                unit_price=float(prices[i] or 0),
                discount_pct=float(line_discounts[i] if i < len(line_discounts) else 0),
            )
            line.recalculate()
            db.session.add(line)

        db.session.flush()
        invoice.recalculate()

        # Post the invoice if requested
        action = request.form.get('action', 'save')
        if action == 'post':
            invoice.status = 'sent'
            entry = _create_invoice_journal(invoice)
            if entry:
                invoice.journal_entry_id = entry.id
                
            # Update Inventory (Stock OUT)
            for line in invoice.lines:
                if line.product_id:
                    prod = Product.query.get(line.product_id)
                    prod.stock_qty = float(prod.stock_qty) - float(line.qty)
                    
                    db.session.add(InventoryMovement(
                        product_id=line.product_id, type='out', qty=line.qty,
                        unit_cost=prod.cost_price, reference=invoice.number,
                        notes=f'مبيعات: {invoice.party.display_name if invoice.party else "عميل نقدي"}',
                        created_by=current_user.id
                    ))
            

            paid_amount = request.form.get('paid_amount', 0, type=float)
            if paid_amount > 0:
                invoice.paid_amount = paid_amount
                if float(invoice.paid_amount) >= float(invoice.total):
                    invoice.paid_amount = invoice.total
                    invoice.status = 'paid'
                else:
                    invoice.status = 'partial'
                
                cash_acc = Account.query.filter_by(code='1110').first()
                ar_acc = Account.query.filter_by(code='1120').first()
                if cash_acc and ar_acc:
                    payment_entry = JournalEntry(
                        date=invoice.date,
                        reference=generate_journal_reference(),
                        description=f'سداد دفعة مقدمة للفاتورة {invoice.number}',
                        created_by=current_user.id, source='invoice', source_id=invoice.id
                    )
                    db.session.add(payment_entry)
                    db.session.flush()
                    db.session.add(JournalLine(entry_id=payment_entry.id, account_id=cash_acc.id, debit=paid_amount, credit=0))
                    db.session.add(JournalLine(entry_id=payment_entry.id, account_id=ar_acc.id, debit=0, credit=paid_amount))

        db.session.commit()
        log_action(current_user.id, 'create', 'Invoice', invoice.id,
                   new_values={'number': invoice.number, 'total': float(invoice.total)})
        flash(f'تم إنشاء الفاتورة {invoice.number} بنجاح', 'success')
        return redirect(url_for('invoices.view', invoice_id=invoice.id))

    return render_template('invoices/form.html', title='فاتورة جديدة',
                           invoice=None, customers=customers, products=products)


@invoices_bp.route('/<int:invoice_id>')
@login_required
def view(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('invoices/view.html', title=f'فاتورة {invoice.number}', invoice=invoice)


@invoices_bp.route('/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('invoices')
def edit(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.status == 'paid':
        flash('لا يمكن تعديل فاتورة مدفوعة', 'error')
        return redirect(url_for('invoices.view', invoice_id=invoice_id))

    customers = Party.query.filter(Party.type.in_(['customer', 'both']), Party.is_active == True).all()
    products = Product.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        old_total = float(invoice.total)
        party_id = request.form.get('party_id', type=int)
        if not party_id:
            flash('الرجاء اختيار العميل بشكل صحيح من القائمة', 'error')
            return redirect(url_for('invoices.edit', invoice_id=invoice.id))
        invoice.party_id = party_id
        inv_date_str = request.form.get('date')
        if inv_date_str:
            invoice.date = datetime.strptime(inv_date_str, '%Y-%m-%d').date()
        due_date_str = request.form.get('due_date')
        invoice.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        invoice.tax_rate = request.form.get('tax_rate', 15, type=float)
        invoice.discount_pct = request.form.get('discount_pct', 0, type=float)
        invoice.notes = request.form.get('notes', '')

        # Delete existing lines
        InvoiceLine.query.filter_by(invoice_id=invoice.id).delete()

        product_ids = request.form.getlist('product_id[]')
        descriptions = request.form.getlist('description[]')
        qtys = request.form.getlist('qty[]')
        prices = request.form.getlist('unit_price[]')
        line_discounts = request.form.getlist('line_discount[]')

        for i, desc in enumerate(descriptions):
            if not desc.strip():
                continue
            line = InvoiceLine(
                invoice_id=invoice.id,
                product_id=int(product_ids[i]) if product_ids[i] else None,
                description=desc.strip(),
                qty=float(qtys[i] or 1),
                unit_price=float(prices[i] or 0),
                discount_pct=float(line_discounts[i] if i < len(line_discounts) else 0),
            )
            line.recalculate()
            db.session.add(line)

        db.session.flush()
        invoice.recalculate()
        db.session.commit()
        log_action(current_user.id, 'update', 'Invoice', invoice.id,
                   old_values={'total': old_total}, new_values={'total': float(invoice.total)})
        flash('تم تحديث الفاتورة بنجاح', 'success')
        return redirect(url_for('invoices.view', invoice_id=invoice.id))

    return render_template('invoices/form.html', title='تعديل الفاتورة',
                           invoice=invoice, customers=customers, products=products)


@invoices_bp.route('/<int:invoice_id>/pay', methods=['POST'])
@login_required
@permission_required('invoices')
def record_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    amount = request.form.get('amount', 0, type=float)
    if amount <= 0:
        flash('المبلغ يجب أن يكون أكبر من صفر', 'error')
        return redirect(url_for('invoices.view', invoice_id=invoice_id))

    invoice.paid_amount = float(invoice.paid_amount) + amount
    if float(invoice.paid_amount) >= float(invoice.total):
        invoice.paid_amount = invoice.total
        invoice.status = 'paid'
    else:
        invoice.status = 'partial'

    # Journal entry for payment
    cash_acc = Account.query.filter_by(code='1110').first()
    ar_acc = Account.query.filter_by(code='1120').first()
    if cash_acc and ar_acc:
        entry = JournalEntry(
            date=date.today(),
            reference=generate_journal_reference(),
            description=f'سداد جزئي للفاتورة {invoice.number}',
            created_by=current_user.id, source='invoice', source_id=invoice.id
        )
        db.session.add(entry)
        db.session.flush()
        db.session.add(JournalLine(entry_id=entry.id, account_id=cash_acc.id, debit=amount, credit=0))
        db.session.add(JournalLine(entry_id=entry.id, account_id=ar_acc.id, debit=0, credit=amount))

    db.session.commit()
    flash(f'تم تسجيل الدفعة {amount:,.2f} ر.س بنجاح', 'success')
    return redirect(url_for('invoices.view', invoice_id=invoice_id))


@invoices_bp.route('/<int:invoice_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    log_action(current_user.id, 'delete', 'Invoice', invoice.id,
               old_values={'number': invoice.number})
    db.session.delete(invoice)
    db.session.commit()
    flash('تم حذف الفاتورة بنجاح', 'success')
    return redirect(url_for('invoices.index'))


@invoices_bp.route('/product-info/<int:product_id>')
@login_required
def product_info(product_id):
    p = Product.query.get_or_404(product_id)
    return jsonify({'name': p.name, 'name_ar': p.name_ar or p.name,
                    'unit_price': float(p.unit_price), 'unit': p.unit})

@invoices_bp.route('/<int:invoice_id>/print/<layout>')
@login_required
def print_invoice(invoice_id, layout):
    invoice = Invoice.query.get_or_404(invoice_id)
    if layout not in ['a4', 'pos']:
        layout = 'a4'
    return render_template('invoices/print_invoice.html', invoice=invoice, layout=layout)

@invoices_bp.route('/export')
@login_required
def export_invoices():
    from ...utils.export import export_to_excel
    invoices = Invoice.query.order_by(Invoice.date.desc()).all()
    headers = ['رقم الفاتورة', 'النوع', 'التاريخ', 'العميل', 'المبلغ الإجمالي', 'المدفوع', 'المتبقي', 'الحالة']
    data = []
    for inv in invoices:
        data.append([
            inv.number,
            inv.type_ar,
            inv.date.strftime('%Y-%m-%d'),
            inv.party.display_name if inv.party else 'عميل نقدي',
            float(inv.total),
            float(inv.paid_amount),
            float(inv.balance_due),
            inv.status_ar
        ])
    return export_to_excel(data, headers, sheet_name='الفواتير', filename_prefix='invoices')
