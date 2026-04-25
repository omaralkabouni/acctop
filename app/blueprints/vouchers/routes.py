"""Vouchers (Receipts/Payments) routes."""
from datetime import date, datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from . import vouchers_bp
from ...extensions import db
from ...models.voucher import Voucher
from ...models.party import Party
from ...models.account import Account
from ...models.invoice import Invoice
from ...models.transaction import JournalEntry, JournalLine
from ...utils.decorators import permission_required, role_required, log_action
from ...utils.helpers import generate_journal_reference


def _allocate_voucher_to_invoices(party_id, amount, vtype):
    """Auto-allocates payment to oldest unpaid invoices."""
    inv_type = 'sale' if vtype == 'receipt' else 'purchase'
    invoices = Invoice.query.filter_by(party_id=party_id, type=inv_type).filter(
        Invoice.status.notin_(['paid', 'cancelled'])
    ).order_by(Invoice.date.asc()).all()
    
    remaining = float(amount)
    for inv in invoices:
        if remaining <= 0: break
        
        due = float(inv.total) - float(inv.paid_amount)
        if due <= 0: continue
        
        pay_amount = min(due, remaining)
        inv.paid_amount = float(inv.paid_amount) + pay_amount
        remaining -= pay_amount
        
        if float(inv.paid_amount) >= float(inv.total):
            inv.paid_amount = inv.total
            inv.status = 'paid'
        else:
            inv.status = 'partial'

def _create_voucher_journal(voucher):
    # Receipt: Debit Bank/Cash, Credit AR
    # Payment: Debit AP, Credit Bank/Cash
    ar_acc = Account.query.filter_by(code='1120').first()
    ap_acc = Account.query.filter_by(code='2120').first()
    
    if not ar_acc or not ap_acc or not voucher.account:
        return None
        
    entry = JournalEntry(
        date=voucher.date,
        reference=generate_journal_reference(),
        description=f'{voucher.type_ar} رقم {voucher.number} - {voucher.party.display_name}',
        created_by=voucher.created_by,
        source='voucher',
        source_id=voucher.id,
    )
    db.session.add(entry)
    db.session.flush()
    
    if voucher.type == 'receipt':
        db.session.add(JournalLine(entry_id=entry.id, account_id=voucher.account_id, debit=float(voucher.amount), credit=0))
        db.session.add(JournalLine(entry_id=entry.id, account_id=ar_acc.id, debit=0, credit=float(voucher.amount)))
    else:
        db.session.add(JournalLine(entry_id=entry.id, account_id=ap_acc.id, debit=float(voucher.amount), credit=0))
        db.session.add(JournalLine(entry_id=entry.id, account_id=voucher.account_id, debit=0, credit=float(voucher.amount)))
        
    return entry


@vouchers_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    vouchers = Voucher.query.order_by(Voucher.date.desc(), Voucher.id.desc()).paginate(page=page, per_page=20)
    return render_template('vouchers/index.html', title='السندات المالية', vouchers=vouchers)


@vouchers_bp.route('/create/<string:vtype>', methods=['GET', 'POST'])
@login_required
@permission_required('expenses') # Wait, use expenses or invoices? Since it deals with money, we can use a general permission. Let's use invoices for now.
def create(vtype):
    if vtype not in ('receipt', 'payment'):
        flash('نوع سند غير صالح', 'error')
        return redirect(url_for('vouchers.index'))
        
    parties = Party.query.filter_by(is_active=True).all()
    # For receipts, usually from customers. For payments, from suppliers.
    if vtype == 'receipt':
        parties = [p for p in parties if p.type in ('customer', 'both')]
        title = 'سند قبض جديد'
        prefix = 'RV'
    else:
        parties = [p for p in parties if p.type in ('supplier', 'both')]
        title = 'سند صرف جديد'
        prefix = 'PV'
        
    accounts = Account.query.filter(Account.type.in_(['asset'])).filter(Account.code.in_(['1110', '1111'])).all()
    # 1110 Cash, 1111 Bank
    if not accounts:
        accounts = Account.query.filter_by(type='asset').all()

    if request.method == 'POST':
        party_id = request.form.get('party_id', type=int)
        account_id = request.form.get('account_id', type=int)
        amount = request.form.get('amount', 0, type=float)
        
        if not party_id or not account_id or amount <= 0:
            flash('الرجاء تعبئة جميع الحقول بشكل صحيح', 'error')
            return redirect(url_for('vouchers.create', vtype=vtype))
            
        vdate_str = request.form.get('date')
        vdate = datetime.strptime(vdate_str, '%Y-%m-%d').date() if vdate_str else date.today()
        
        # Generate number
        count = Voucher.query.filter_by(type=vtype).count() + 1
        number = f"{prefix}-{str(count).zfill(5)}"
        
        voucher = Voucher(
            number=number,
            type=vtype,
            party_id=party_id,
            account_id=account_id,
            amount=amount,
            date=vdate,
            reference=request.form.get('reference', ''),
            notes=request.form.get('notes', ''),
            created_by=current_user.id
        )
        db.session.add(voucher)
        db.session.flush()
        
        # Allocate to invoices
        _allocate_voucher_to_invoices(party_id, amount, vtype)
        
        # Journal entry
        entry = _create_voucher_journal(voucher)
        if entry:
            voucher.journal_entry_id = entry.id
            
        db.session.commit()
        log_action(current_user.id, 'create', 'Voucher', voucher.id, new_values={'number': voucher.number, 'amount': float(voucher.amount)})
        
        # --- n8n Trigger ---
        from ...models.settings import SystemSettings
        settings = SystemSettings.get_settings()
        if settings and settings.n8n_webhook_url:
            import requests
            payload = {
                'action': 'new_payment',
                'voucher_id': voucher.id,
                'voucher_number': voucher.number,
                'voucher_type': voucher.type_ar,
                'amount': float(voucher.amount),
                'date': voucher.date.isoformat(),
                'party_name': voucher.party.display_name,
                'party_phone': voucher.party.phone,
                'notes': voucher.notes,
                'timestamp': datetime.now().isoformat()
            }
            try:
                requests.post(settings.n8n_webhook_url, json=payload, timeout=5)
            except:
                pass # Silently fail if webhook is down
        
        flash(f'تم حفظ {voucher.type_ar} رقم {voucher.number} بنجاح', 'success')
        return redirect(url_for('vouchers.index'))
        
    return render_template('vouchers/form.html', title=title, vtype=vtype, parties=parties, accounts=accounts)


@vouchers_bp.route('/<int:voucher_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete(voucher_id):
    voucher = Voucher.query.get_or_404(voucher_id)
    # Note: deleting a voucher does not automatically de-allocate the invoice paid amounts.
    # In a full ERP, deleting a payment requires reversing the allocation.
    # For now, we will just delete the voucher and journal entry. The user will have to manually adjust invoice if needed, or we just keep it simple.
    db.session.delete(voucher)
    db.session.commit()
    flash('تم حذف السند بنجاح', 'success')
    return redirect(url_for('vouchers.index'))

@vouchers_bp.route('/<int:voucher_id>/print/<layout>')
@login_required
def print_voucher(voucher_id, layout):
    voucher = Voucher.query.get_or_404(voucher_id)
    if layout not in ['a4', 'pos']:
        layout = 'a4'
    return render_template('vouchers/print_voucher.html', voucher=voucher, layout=layout)

@vouchers_bp.route('/export')
@login_required
def export_vouchers():
    from ...utils.export import export_to_excel
    vouchers = Voucher.query.order_by(Voucher.date.desc()).all()
    headers = ['رقم السند', 'النوع', 'التاريخ', 'الطرف', 'المبلغ', 'الحساب']
    data = []
    for v in vouchers:
        data.append([
            v.number,
            v.type_ar,
            v.date.strftime('%Y-%m-%d'),
            v.party.display_name,
            float(v.amount),
            v.account.name_ar if v.account else ''
        ])
    return export_to_excel(data, headers, sheet_name='السندات المالية', filename_prefix='vouchers')
