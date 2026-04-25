"""Dashboard routes — KPIs and chart data."""
from datetime import date, timedelta
from flask import render_template, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from . import dashboard_bp
from ...extensions import db
from ...models.invoice import Invoice
from ...models.expense import Expense
from ...models.product import Product
from ...models.party import Party
from ...models.transaction import JournalEntry
from ...models.audit import AuditLog


@dashboard_bp.route('/')
@login_required
def index():
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # --- KPIs ---
    # Revenue (paid + partial sales invoices)
    revenue = db.session.query(
        func.coalesce(func.sum(Invoice.paid_amount), 0)
    ).filter(
        Invoice.type == 'sale',
        Invoice.status.in_(['paid', 'partial']),
        Invoice.date >= month_start
    ).scalar() or 0

    # Expenses this month
    expenses_total = db.session.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(Expense.date >= month_start).scalar() or 0

    # Outstanding invoices (total due not yet paid)
    outstanding = db.session.query(
        func.coalesce(func.sum(Invoice.total - Invoice.paid_amount), 0)
    ).filter(
        Invoice.type == 'sale',
        Invoice.status.in_(['sent', 'partial', 'overdue'])
    ).scalar() or 0

    net_profit = float(revenue) - float(expenses_total)

    # --- Invoice status counts ---
    invoice_stats = db.session.query(
        Invoice.status, func.count(Invoice.id)
    ).filter(Invoice.type == 'sale').group_by(Invoice.status).all()
    invoice_status = {s: c for s, c in invoice_stats}
    total_invoices = sum(invoice_status.values())

    # --- Monthly cash flow (last 6 months) ---
    monthly_data = []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        if i == 0:
            m_end = today
        else:
            next_m = (m_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            m_end = next_m - timedelta(days=1)

        m_rev = db.session.query(
            func.coalesce(func.sum(Invoice.paid_amount), 0)
        ).filter(
            Invoice.type == 'sale',
            Invoice.date >= m_start, Invoice.date <= m_end,
            Invoice.status.in_(['paid', 'partial'])
        ).scalar() or 0

        m_exp = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(Expense.date >= m_start, Expense.date <= m_end).scalar() or 0

        ar_months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                     'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
        monthly_data.append({
            'month': ar_months[m_start.month - 1],
            'revenue': float(m_rev),
            'expenses': float(m_exp),
        })

    # --- Low stock products ---
    low_stock = Product.query.filter(
        Product.stock_qty <= Product.min_stock, Product.is_active == True
    ).limit(5).all()

    # --- Recent invoices ---
    recent_invoices = Invoice.query.filter_by(type='sale').order_by(
        Invoice.created_at.desc()
    ).limit(5).all()

    # --- Recent audit log ---
    recent_activity = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(8).all()

    # --- Top customers by balance ---
    top_customers = Party.query.filter_by(type='customer', is_active=True).limit(5).all()

    return render_template('dashboard/index.html',
                           title='لوحة التحكم',
                           revenue=revenue,
                           expenses_total=expenses_total,
                           outstanding=outstanding,
                           net_profit=net_profit,
                           invoice_status=invoice_status,
                           total_invoices=total_invoices,
                           monthly_data=monthly_data,
                           low_stock=low_stock,
                           recent_invoices=recent_invoices,
                           recent_activity=recent_activity,
                           top_customers=top_customers)


@dashboard_bp.route('/api/chart-data')
@login_required
def chart_data():
    """JSON endpoint for dashboard charts."""
    today = date.today()
    monthly_data = []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        m_end = today if i == 0 else (m_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        m_rev = db.session.query(func.coalesce(func.sum(Invoice.paid_amount), 0)).filter(
            Invoice.type == 'sale', Invoice.date >= m_start, Invoice.date <= m_end
        ).scalar() or 0

        m_exp = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            Expense.date >= m_start, Expense.date <= m_end
        ).scalar() or 0

        ar_months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                     'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
        monthly_data.append({'month': ar_months[m_start.month - 1],
                              'revenue': float(m_rev), 'expenses': float(m_exp)})

    return jsonify(monthly_data)
