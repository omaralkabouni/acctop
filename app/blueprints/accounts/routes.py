"""Accounts routes — Chart of Accounts and Journal Entries."""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from . import accounts_bp
from ...extensions import db
from ...models.account import Account
from ...models.transaction import JournalEntry, JournalLine
from ...utils.decorators import permission_required, role_required, log_action
from ...utils.helpers import generate_journal_reference


@accounts_bp.route('/')
@login_required
def index():
    accounts = Account.query.filter_by(parent_id=None).order_by(Account.code).all()
    return render_template('accounts/index.html', title='دليل الحسابات', accounts=accounts)


@accounts_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('accounts')
def create_account():
    parent_accounts = Account.query.order_by(Account.code).all()
    if request.method == 'POST':
        acc = Account(
            code=request.form.get('code', '').strip(),
            name_ar=request.form.get('name_ar', '').strip(),
            name_en=request.form.get('name_en', '').strip(),
            type=request.form.get('type'),
            parent_id=request.form.get('parent_id', None, type=int),
            description=request.form.get('description', '').strip(),
        )
        if Account.query.filter_by(code=acc.code).first():
            flash('كود الحساب موجود بالفعل', 'error')
        else:
            db.session.add(acc)
            db.session.commit()
            log_action(current_user.id, 'create', 'Account', acc.id,
                       new_values={'code': acc.code, 'name_ar': acc.name_ar})
            flash(f'تم إنشاء الحساب {acc.name_ar} بنجاح', 'success')
            return redirect(url_for('accounts.index'))
    return render_template('accounts/account_form.html', title='إضافة حساب',
                           account=None, parent_accounts=parent_accounts)


@accounts_bp.route('/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('accounts')
def edit_account(account_id):
    acc = Account.query.get_or_404(account_id)
    parent_accounts = Account.query.filter(Account.id != account_id).order_by(Account.code).all()
    if request.method == 'POST':
        old_vals = {'name_ar': acc.name_ar, 'type': acc.type}
        acc.name_ar = request.form.get('name_ar', acc.name_ar).strip()
        acc.name_en = request.form.get('name_en', acc.name_en).strip()
        acc.type = request.form.get('type', acc.type)
        acc.parent_id = request.form.get('parent_id', None, type=int)
        acc.description = request.form.get('description', '').strip()
        acc.is_active = bool(request.form.get('is_active'))
        db.session.commit()
        log_action(current_user.id, 'update', 'Account', acc.id, old_values=old_vals,
                   new_values={'name_ar': acc.name_ar})
        flash('تم تحديث الحساب بنجاح', 'success')
        return redirect(url_for('accounts.index'))
    return render_template('accounts/account_form.html', title='تعديل حساب',
                           account=acc, parent_accounts=parent_accounts)


# ---- Journal Entries ----

@accounts_bp.route('/journal')
@login_required
def journal():
    page = request.args.get('page', 1, type=int)
    entries = JournalEntry.query.order_by(JournalEntry.date.desc()).paginate(page=page, per_page=20)
    return render_template('accounts/journal.html', title='دفتر الأستاذ العام',
                           entries=entries)


@accounts_bp.route('/journal/create', methods=['GET', 'POST'])
@login_required
@permission_required('accounts')
def create_journal_entry():
    all_accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    if request.method == 'POST':
        entry_date = request.form.get('date')
        description = request.form.get('description', '').strip()
        reference = request.form.get('reference') or generate_journal_reference()

        account_ids = request.form.getlist('account_id[]')
        debits = request.form.getlist('debit[]')
        credits = request.form.getlist('credit[]')
        line_descs = request.form.getlist('line_description[]')

        entry = JournalEntry(
            date=entry_date,
            description=description,
            reference=reference,
            created_by=current_user.id,
            source='manual',
        )
        db.session.add(entry)
        db.session.flush()

        total_debit = 0
        total_credit = 0
        for i, acc_id in enumerate(account_ids):
            if not acc_id:
                continue
            d = float(debits[i] or 0)
            c = float(credits[i] or 0)
            line = JournalLine(
                entry_id=entry.id,
                account_id=int(acc_id),
                debit=d,
                credit=c,
                description=line_descs[i] if i < len(line_descs) else '',
            )
            db.session.add(line)
            total_debit += d
            total_credit += c

        if abs(total_debit - total_credit) > 0.001:
            db.session.rollback()
            flash('القيد غير متوازن! يجب أن يتساوى مجموع المدين مع مجموع الدائن.', 'error')
            return render_template('accounts/journal_form.html', title='قيد يومية جديد',
                                   accounts=all_accounts)

        db.session.commit()
        log_action(current_user.id, 'create', 'JournalEntry', entry.id,
                   new_values={'reference': entry.reference, 'description': description})
        flash(f'تم حفظ القيد {entry.reference} بنجاح', 'success')
        return redirect(url_for('accounts.journal'))

    return render_template('accounts/journal_form.html', title='قيد يومية جديد',
                           accounts=all_accounts)


@accounts_bp.route('/journal/<int:entry_id>')
@login_required
def view_journal_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    return render_template('accounts/journal_detail.html', title=f'قيد {entry.reference}',
                           entry=entry)


@accounts_bp.route('/journal/<int:entry_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_journal_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    log_action(current_user.id, 'delete', 'JournalEntry', entry.id,
               old_values={'reference': entry.reference})
    db.session.delete(entry)
    db.session.commit()
    flash('تم حذف القيد بنجاح', 'success')
    return redirect(url_for('accounts.journal'))
