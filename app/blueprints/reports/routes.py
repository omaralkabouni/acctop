"""Reports routes — P&L, General Ledger, Debt, Inventory."""
from datetime import date
from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func

from . import reports_bp
from ...extensions import db
from ...models.invoice import Invoice
from ...models.expense import Expense
from ...models.account import Account
from ...models.transaction import JournalEntry, JournalLine
from ...models.party import Party
from ...models.product import Product, InventoryMovement
from ...models.audit import AuditLog
from ...models.user import User
from ...utils.helpers import get_date_range
from ...utils.export import export_to_excel
from ...utils.decorators import role_required


@reports_bp.route('/')
@login_required
def index():
    return render_template('reports/index.html', title='التقارير')


@reports_bp.route('/profit-loss')
@login_required
def profit_loss():
    period = request.args.get('period', 'month')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if start_date_str and end_date_str:
        from datetime import datetime
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        start_date, end_date = get_date_range(period)

    # Revenue from paid invoices
    revenue = db.session.query(
        func.coalesce(func.sum(Invoice.paid_amount), 0)
    ).filter(
        Invoice.type == 'sale',
        Invoice.date >= start_date,
        Invoice.date <= end_date,
        Invoice.status.in_(['paid', 'partial'])
    ).scalar() or 0

    # Total invoiced (including unpaid)
    total_invoiced = db.session.query(
        func.coalesce(func.sum(Invoice.total), 0)
    ).filter(
        Invoice.type == 'sale',
        Invoice.date >= start_date,
        Invoice.date <= end_date,
        Invoice.status.notin_(['draft', 'cancelled'])
    ).scalar() or 0

    # Expenses by category
    from ...models.expense import ExpenseCategory
    expense_by_cat = db.session.query(
        ExpenseCategory.name, func.sum(Expense.amount)
    ).join(Expense, Expense.category_id == ExpenseCategory.id, isouter=True).filter(
        Expense.date >= start_date, Expense.date <= end_date
    ).group_by(ExpenseCategory.name).all()

    total_expenses = sum(amt for _, amt in expense_by_cat if amt)
    net_profit = float(revenue) - float(total_expenses)
    profit_margin = (net_profit / float(revenue) * 100) if float(revenue) > 0 else 0

    return render_template('reports/profit_loss.html',
                           title='تقرير الربح والخسارة',
                           revenue=revenue, total_invoiced=total_invoiced,
                           expense_by_cat=expense_by_cat,
                           total_expenses=total_expenses,
                           net_profit=net_profit,
                           profit_margin=profit_margin,
                           start_date=start_date, end_date=end_date,
                           period=period)


@reports_bp.route('/general-ledger')
@login_required
def general_ledger():
    account_id = request.args.get('account_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    period = request.args.get('period', 'month')

    if start_date_str and end_date_str:
        from datetime import datetime
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        start_date, end_date = get_date_range(period)

    accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    selected_account = Account.query.get(account_id) if account_id else None

    lines = []
    if selected_account:
        lines = db.session.query(JournalLine, JournalEntry).join(
            JournalEntry, JournalLine.entry_id == JournalEntry.id
        ).filter(
            JournalLine.account_id == account_id,
            JournalEntry.date >= start_date,
            JournalEntry.date <= end_date,
        ).order_by(JournalEntry.date).all()

    if request.args.get('export') and selected_account:
        from ...utils.export import export_to_excel
        headers = ['التاريخ', 'رقم القيد', 'البيان', 'مدين', 'دائن']
        data = []
        for line, entry in lines:
            data.append([
                entry.date.strftime('%Y-%m-%d'),
                entry.reference,
                entry.description,
                float(line.debit),
                float(line.credit)
            ])
        return export_to_excel(data, headers, sheet_name='دفتر الأستاذ', filename_prefix=f'gl_{selected_account.code}')

    return render_template('reports/general_ledger.html',
                           title='دفتر الأستاذ العام',
                           accounts=accounts,
                           selected_account=selected_account,
                           lines=lines,
                           start_date=start_date, end_date=end_date)


@reports_bp.route('/debt')
@login_required
def debt_report():
    # Accounts Receivable (customers who owe us)
    customers = Party.query.filter(
        Party.type.in_(['customer', 'both']),
        Party.is_active == True
    ).all()
    receivables = [(c, c.balance) for c in customers if c.balance > 0.01]
    total_receivable = sum(b for _, b in receivables)

    # Accounts Payable (suppliers we owe)
    suppliers = Party.query.filter(
        Party.type.in_(['supplier', 'both']),
        Party.is_active == True
    ).all()
    payables = []
    for s in suppliers:
        bal = sum(
            float(inv.total) - float(inv.paid_amount)
            for inv in s.invoices.filter_by(type='purchase')
            if inv.status not in ('draft', 'cancelled')
        )
        if bal > 0.01:
            payables.append((s, bal))
    total_payable = sum(b for _, b in payables)

    if request.args.get('export'):
        from ...utils.export import export_to_excel
        headers = ['الاسم', 'النوع', 'المبلغ المستحق']
        data = []
        for c, b in receivables:
            data.append([c.display_name, 'عميل', float(b)])
        for s, b in payables:
            data.append([s.display_name, 'مورد', float(b)])
        return export_to_excel(data, headers, sheet_name='الديون', filename_prefix='debt_report')

    return render_template('reports/debt.html',
                           title='تقرير الديون',
                           receivables=receivables,
                           payables=payables,
                           total_receivable=total_receivable,
                           total_payable=total_payable)


@reports_bp.route('/inventory')
@login_required
def inventory_report():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    total_value = sum(p.stock_value for p in products)
    low_stock = [p for p in products if p.is_low_stock]

    if request.args.get('export'):
        from ...utils.export import export_to_excel
        headers = ['الصنف', 'الباركود', 'الكمية الحالية', 'سعر البيع', 'قيمة المخزون']
        data = []
        for p in products:
            data.append([p.name_ar or p.name, p.sku or '', float(p.stock_qty), float(p.unit_price), float(p.stock_value)])
        return export_to_excel(data, headers, sheet_name='المخزون', filename_prefix='inventory_report')

    return render_template('reports/inventory.html',
                           title='تقرير المخزون',
                           products=products,
                           total_value=total_value,
                           low_stock=low_stock)

@reports_bp.route('/party-statement')
@login_required
def party_statement():
    from ...models.voucher import Voucher
    
    party_id = request.args.get('party_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    period = request.args.get('period', 'month')

    if start_date_str and end_date_str:
        from datetime import datetime
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        start_date, end_date = get_date_range(period)

    parties = Party.query.filter_by(is_active=True).order_by(Party.name_ar, Party.name).all()
    selected_party = Party.query.get(party_id) if party_id else None

    statement_lines = []
    total_debit = 0.0
    total_credit = 0.0

    if selected_party:
        # Get invoices
        invoices = selected_party.invoices.filter(
            Invoice.date >= start_date,
            Invoice.date <= end_date,
            Invoice.status.notin_(['draft', 'cancelled'])
        ).all()
        
        # Get vouchers
        vouchers = selected_party.vouchers.filter(
            Voucher.date >= start_date,
            Voucher.date <= end_date
        ).all()
        
        # Combine and sort chronologically
        for inv in invoices:
            is_sale = (inv.type == 'sale')
            debit = float(inv.total) if is_sale else 0.0
            credit = float(inv.total) if not is_sale else 0.0
            statement_lines.append({
                'date': inv.date,
                'type': 'فاتورة مبيعات' if is_sale else 'فاتورة مشتريات',
                'reference': inv.number,
                'debit': debit,
                'credit': credit,
                'notes': inv.notes,
                'obj_id': inv.id,
                'is_invoice': True
            })
            total_debit += debit
            total_credit += credit
            
        for v in vouchers:
            is_receipt = (v.type == 'receipt')
            # For a customer/supplier: 
            # Receipt (we get money) -> Credit to their account (decreases debt)
            # Payment (we pay them) -> Debit to their account
            debit = float(v.amount) if not is_receipt else 0.0
            credit = float(v.amount) if is_receipt else 0.0
            statement_lines.append({
                'date': v.date,
                'type': 'سند قبض' if is_receipt else 'سند صرف',
                'reference': v.number,
                'debit': debit,
                'credit': credit,
                'notes': v.notes,
                'obj_id': v.id,
                'is_invoice': False
            })
            total_debit += debit
            total_credit += credit
            
        # Sort by date
        statement_lines.sort(key=lambda x: x['date'])
        
        # Calculate running balance
        # For customers: Balance = Debit - Credit
        # For suppliers: Balance = Credit - Debit
        # To make it universal, we usually do Running Balance = Debit - Credit. 
        # If it's a supplier, a negative balance means we owe them.
        running_bal = 0.0
        for line in statement_lines:
            running_bal += line['debit'] - line['credit']
            line['balance'] = running_bal

    if request.args.get('export'):
        from ...utils.export import export_to_excel
        headers = ['التاريخ', 'النوع', 'رقم المرجع', 'البيان', 'لنا', 'له', 'المتبقي']
        data = []
        for line in statement_lines:
            data.append([
                line['date'].strftime('%Y-%m-%d'),
                line['type'],
                line['reference'],
                line['notes'] or '',
                float(line['debit']),
                float(line['credit']),
                float(line['balance'])
            ])
        return export_to_excel(data, headers, sheet_name='كشف حساب', filename_prefix=f'party_statement_{selected_party.id if selected_party else ""}')

    return render_template('reports/party_statement.html',
                           title='كشف حساب عميل / مورد',
                           parties=parties,
                           selected_party=selected_party,
                           lines=statement_lines,
                           total_debit=total_debit,
                           total_credit=total_credit,
                           final_balance=total_debit - total_credit,
                           start_date=start_date, end_date=end_date)


@reports_bp.route('/profit-loss/export')
@login_required
def export_profit_loss():
    period = request.args.get('period', 'month')
    start_date, end_date = get_date_range(period)

    from ...models.expense import ExpenseCategory
    revenue = db.session.query(func.coalesce(func.sum(Invoice.paid_amount), 0)).filter(
        Invoice.type == 'sale', Invoice.date >= start_date, Invoice.date <= end_date
    ).scalar() or 0

    expense_by_cat = db.session.query(
        ExpenseCategory.name, func.sum(Expense.amount)
    ).join(Expense, Expense.category_id == ExpenseCategory.id, isouter=True).filter(
        Expense.date >= start_date, Expense.date <= end_date
    ).group_by(ExpenseCategory.name).all()

    total_expenses = sum(float(amt) for _, amt in expense_by_cat if amt)
    net_profit = float(revenue) - total_expenses

    headers = ['البند', 'المبلغ (ر.س)']
    data = [['إجمالي الإيرادات', f'{float(revenue):,.2f}']]
    for cat, amt in expense_by_cat:
        data.append([f'مصروف: {cat}', f'{float(amt or 0):,.2f}'])
    data.append(['صافي الربح', f'{net_profit:,.2f}'])

    return export_to_excel(data, headers, sheet_name='P&L', filename_prefix='profit_loss')

@reports_bp.route('/audit-log')
@login_required
@role_required('admin')
def audit_log():
    page = request.args.get('page', 1, type=int)
    user_id = request.args.get('user_id', type=int)
    
    query = AuditLog.query.order_by(AuditLog.timestamp.desc())
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
        
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    users = User.query.filter_by(is_active=True).all()
    
    return render_template('reports/audit_log.html',
                           title='سجل نشاطات المستخدمين',
                           pagination=pagination,
                           users=users,
                           selected_user=user_id)
