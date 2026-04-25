"""Parties routes — customers and suppliers CRUD."""
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from . import parties_bp
from ...extensions import db
from ...models.party import Party
from ...utils.decorators import permission_required, role_required, log_action


@parties_bp.route('/')
@login_required
def index():
    party_type = request.args.get('type', '')
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    q = Party.query.filter_by(is_active=True)
    if party_type:
        q = q.filter(Party.type.in_([party_type, 'both']))
    if search:
        q = q.filter(Party.name.ilike(f'%{search}%') | Party.email.ilike(f'%{search}%'))

    parties = q.order_by(Party.name).paginate(page=page, per_page=25)
    return render_template('parties/index.html', title='العملاء والموردون',
                           parties=parties, party_type=party_type, search=search)


@parties_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('parties')
def create():
    if request.method == 'POST':
        party = Party(
            type=request.form.get('type', 'customer'),
            name=request.form.get('name', '').strip(),
            name_ar=request.form.get('name_ar', '').strip() or None,
            phone=request.form.get('phone', '').strip() or None,
            email=request.form.get('email', '').strip() or None,
            address=request.form.get('address', '').strip() or None,
            tax_number=request.form.get('tax_number', '').strip() or None,
            credit_limit=float(request.form.get('credit_limit', 0)),
            notes=request.form.get('notes', '').strip(),
        )
        db.session.add(party)
        db.session.commit()
        log_action(current_user.id, 'create', 'Party', party.id,
                   new_values={'name': party.name, 'type': party.type})
        flash(f'تم إضافة {party.type_ar} {party.display_name} بنجاح', 'success')
        return redirect(url_for('parties.index'))
    return render_template('parties/form.html', title='إضافة عميل/مورد', party=None)


@parties_bp.route('/<int:party_id>')
@login_required
def view(party_id):
    party = Party.query.get_or_404(party_id)
    from ...models.invoice import Invoice
    invoices = Invoice.query.filter_by(party_id=party_id).order_by(Invoice.date.desc()).limit(20).all()
    return render_template('parties/view.html', title=party.display_name,
                           party=party, invoices=invoices)


@parties_bp.route('/<int:party_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('parties')
def edit(party_id):
    party = Party.query.get_or_404(party_id)
    if request.method == 'POST':
        old_vals = {'name': party.name, 'type': party.type}
        party.type = request.form.get('type', party.type)
        party.name = request.form.get('name', party.name).strip()
        party.name_ar = request.form.get('name_ar', '').strip() or None
        party.phone = request.form.get('phone', '').strip() or None
        party.email = request.form.get('email', '').strip() or None
        party.address = request.form.get('address', '').strip() or None
        party.tax_number = request.form.get('tax_number', '').strip() or None
        party.credit_limit = float(request.form.get('credit_limit', party.credit_limit))
        party.notes = request.form.get('notes', '').strip()
        party.is_active = bool(request.form.get('is_active'))
        db.session.commit()
        log_action(current_user.id, 'update', 'Party', party.id, old_values=old_vals,
                   new_values={'name': party.name})
        flash('تم التحديث بنجاح', 'success')
        return redirect(url_for('parties.view', party_id=party.id))
    return render_template('parties/form.html', title='تعديل', party=party)


@parties_bp.route('/<int:party_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete(party_id):
    party = Party.query.get_or_404(party_id)
    party.is_active = False
    db.session.commit()
    flash('تم أرشفة العميل/المورد', 'success')
    return redirect(url_for('parties.index'))

@parties_bp.route('/<int:party_id>/statement')
@login_required
def statement(party_id):
    party = Party.query.get_or_404(party_id)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    from ...models.invoice import Invoice
    from ...models.transaction import JournalLine, JournalEntry
    from ...models.account import Account
    
    # Get AR/AP account for this party
    # Simplified: we just look for transactions where this party is involved
    # or just use Invoices for now as it's the primary source
    
    invoices = Invoice.query.filter_by(party_id=party_id).order_by(Invoice.date.asc()).all()
    
    entries = []
    running_balance = 0
    
    for inv in invoices:
        # If it's a sale, it increases what they owe us (+)
        # If it's a purchase, it increases what we owe them (-)
        # Let's keep it simple: Balance = Sum(Sales) - Sum(Purchases) - Sum(Payments Received)
        
        amount = float(inv.total)
        if inv.type == 'sale':
            running_balance += amount
            entries.append({
                'date': inv.date,
                'description': f'فاتورة مبيعات رقم {inv.number}',
                'debit': amount,
                'credit': 0,
                'balance': running_balance
            })
            # Also handle payments for this invoice
            # (In this simple ERP, payments might be separate)
        elif inv.type == 'purchase':
            running_balance -= amount
            entries.append({
                'date': inv.date,
                'description': f'فاتورة مشتريات رقم {inv.number}',
                'debit': 0,
                'credit': amount,
                'balance': running_balance
            })
            
    return render_template('parties/statement.html', title=f'كشف حساب - {party.display_name}',
                           party=party, entries=entries, balance=running_balance)

@parties_bp.route('/<int:party_id>/api/send-statement', methods=['POST'])
@login_required
def api_send_statement(party_id):
    party = Party.query.get_or_404(party_id)
    
    from ...models.settings import SystemSettings
    settings = SystemSettings.get_settings()
    
    if not settings or not settings.n8n_webhook_url:
        return jsonify({'success': False, 'error': 'لم يتم تكوين رابط n8n في الإعدادات'}), 400
        
    import requests
    from ...models.invoice import Invoice
    
    # Calculate full statement lines for the payload
    invoices = Invoice.query.filter_by(party_id=party.id).order_by(Invoice.date.asc()).all()
    lines = []
    bal = 0
    for inv in invoices:
        amount = float(inv.total)
        is_sale = (inv.type == 'sale')
        if is_sale: bal += amount
        else: bal -= amount
        lines.append({
            'date': inv.date.isoformat(),
            'description': f'فاتورة مبيعات رقم {inv.number}' if is_sale else f'فاتورة مشتريات رقم {inv.number}',
            'debit': amount if is_sale else 0,
            'credit': amount if not is_sale else 0,
            'balance': bal
        })

    payload = {
        'action': 'account_statement',
        'party_id': party.id,
        'party_name': party.display_name,
        'party_phone': party.phone,
        'party_email': party.email,
        'balance': float(party.balance),
        'statement_lines': lines,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        r = requests.post(settings.n8n_webhook_url, json=payload, timeout=10)
        if r.status_code in [200, 201]:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': f'رد n8n غير متوقع: {r.status_code}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
