"""Expenses routes."""
from datetime import date
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from . import expenses_bp
from ...extensions import db
from ...models.expense import Expense, ExpenseCategory
from ...models.account import Account
from ...models.party import Party
from ...models.transaction import JournalEntry, JournalLine
from ...utils.decorators import permission_required, role_required, log_action
from ...utils.helpers import generate_journal_reference


def _expense_journal(expense):
    exp_acc = expense.account or Account.query.filter_by(code='5300').first()
    cash_acc = Account.query.filter_by(code='1110').first()
    if not exp_acc or not cash_acc:
        return
    entry = JournalEntry(
        date=expense.date,
        reference=generate_journal_reference(),
        description=f'مصروف: {expense.description}',
        created_by=expense.created_by,
        source='expense',
        source_id=expense.id,
    )
    db.session.add(entry)
    db.session.flush()
    db.session.add(JournalLine(entry_id=entry.id, account_id=exp_acc.id,
                                debit=float(expense.amount), credit=0))
    db.session.add(JournalLine(entry_id=entry.id, account_id=cash_acc.id,
                                debit=0, credit=float(expense.amount)))
    expense.journal_entry_id = entry.id


@expenses_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', type=int)
    search = request.args.get('q', '')

    q = Expense.query
    if category_id:
        q = q.filter_by(category_id=category_id)
    if search:
        q = q.filter(Expense.description.ilike(f'%{search}%'))

    expenses = q.order_by(Expense.id.desc()).paginate(page=page, per_page=25)
    categories = ExpenseCategory.query.all()
    total = sum(float(e.amount) for e in Expense.query.all())
    return render_template('expenses/index.html', title='المصروفات',
                           expenses=expenses, categories=categories,
                           total=total, category_id=category_id, search=search)


@expenses_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('expenses')
def create():
    categories = ExpenseCategory.query.all()
    accounts = Account.query.filter_by(type='expense', is_active=True).all()
    suppliers = Party.query.filter(Party.type.in_(['supplier', 'both'])).all()

    if request.method == 'POST':
        exp_date_str = request.form.get('date')
        from datetime import datetime
        exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d').date() if exp_date_str else date.today()

        expense = Expense(
            category_id=request.form.get('category_id', type=int),
            account_id=request.form.get('account_id', type=int),
            party_id=request.form.get('party_id', type=int) or None,
            amount=float(request.form.get('amount', 0)),
            date=exp_date,
            description=request.form.get('description', '').strip(),
            payment_method=request.form.get('payment_method', 'cash'),
            is_paid=bool(request.form.get('is_paid', True)),
            created_by=current_user.id,
        )
        db.session.add(expense)
        db.session.flush()
        _expense_journal(expense)
        db.session.commit()
        log_action(current_user.id, 'create', 'Expense', expense.id,
                   new_values={'description': expense.description, 'amount': float(expense.amount)})
        flash('تم إضافة المصروف بنجاح', 'success')
        return redirect(url_for('expenses.index'))

    return render_template('expenses/form.html', title='إضافة مصروف',
                           expense=None, categories=categories, accounts=accounts, suppliers=suppliers)


@expenses_bp.route('/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('expenses')
def edit(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    categories = ExpenseCategory.query.all()
    accounts = Account.query.filter_by(type='expense', is_active=True).all()
    suppliers = Party.query.filter(Party.type.in_(['supplier', 'both'])).all()

    if request.method == 'POST':
        old_vals = {'amount': float(expense.amount), 'description': expense.description}
        expense.category_id = request.form.get('category_id', type=int)
        expense.account_id = request.form.get('account_id', type=int)
        expense.party_id = request.form.get('party_id', type=int) or None
        expense.amount = float(request.form.get('amount', expense.amount))
        exp_date_str = request.form.get('date')
        if exp_date_str:
            from datetime import datetime
            expense.date = datetime.strptime(exp_date_str, '%Y-%m-%d').date()
        expense.description = request.form.get('description', expense.description).strip()
        expense.payment_method = request.form.get('payment_method', expense.payment_method)
        db.session.commit()
        log_action(current_user.id, 'update', 'Expense', expense.id, old_values=old_vals,
                   new_values={'amount': float(expense.amount)})
        flash('تم تحديث المصروف بنجاح', 'success')
        return redirect(url_for('expenses.index'))

    return render_template('expenses/form.html', title='تعديل مصروف',
                           expense=expense, categories=categories, accounts=accounts, suppliers=suppliers)


@expenses_bp.route('/<int:expense_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    log_action(current_user.id, 'delete', 'Expense', expense.id,
               old_values={'description': expense.description})
    db.session.delete(expense)
    db.session.commit()
    flash('تم حذف المصروف', 'success')
    return redirect(url_for('expenses.index'))

@expenses_bp.route('/export')
@login_required
def export_expenses():
    from ...utils.export import export_to_excel
    expenses = Expense.query.order_by(Expense.date.desc()).all()
    headers = ['التاريخ', 'الوصف', 'الفئة', 'المبلغ', 'طريقة الدفع', 'المورد']
    data = []
    for exp in expenses:
        data.append([
            exp.date.strftime('%Y-%m-%d'),
            exp.description,
            exp.category.name if exp.category else '',
            float(exp.amount),
            exp.payment_method,
            exp.party.display_name if exp.party else ''
        ])
    return export_to_excel(data, headers, sheet_name='المصروفات', filename_prefix='expenses')
