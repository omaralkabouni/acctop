"""Shared helper utilities for formatting and calculations."""
from datetime import datetime
import locale


def format_currency(amount, currency=None):
    """Format a number as currency with Arabic locale style."""
    if currency is None:
        from ..models.settings import SystemSettings
        try:
            # We use a simple query here, it will be cached by SQLAlchemy in most cases
            settings = SystemSettings.query.first()
            currency = settings.currency_symbol if settings else 'ر.س'
        except:
            currency = 'ر.س'
            
    try:
        val = float(amount)
        formatted = f'{val:,.2f}'
        if formatted.endswith('.00'):
            formatted = formatted[:-3]
        elif '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')
        return f'{formatted} {currency}'
    except (TypeError, ValueError):
        return f'0 {currency}'


def rzero(n):
    """Remove trailing zeros from a number for display."""
    try:
        val = float(n)
        if val == int(val):
            return str(int(val))
        return str(val).rstrip('0').rstrip('.')
    except:
        return n

def format_date(date_obj, fmt='%Y-%m-%d'):
    """Format a date object to string."""
    if not date_obj:
        return ''
    if isinstance(date_obj, str):
        return date_obj
    return date_obj.strftime(fmt)


def arabic_number(n):
    """Convert western digits to Arabic-Indic numerals."""
    arabic_digits = '٠١٢٣٤٥٦٧٨٩'
    return ''.join(arabic_digits[int(c)] if c.isdigit() else c for c in str(n))


def generate_invoice_number(prefix='INV'):
    """Generate a sequential invoice number."""
    from ..models.invoice import Invoice
    last = Invoice.query.order_by(Invoice.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    return f'{prefix}-{next_id:05d}'


def generate_journal_reference():
    """Generate a sequential journal reference."""
    from ..models.transaction import JournalEntry
    last = JournalEntry.query.order_by(JournalEntry.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    year = datetime.utcnow().strftime('%Y')
    return f'JE-{year}-{next_id:05d}'


def get_date_range(period='month'):
    """Return (start_date, end_date) for a given period string."""
    from datetime import date, timedelta
    today = date.today()
    if period == 'day':
        return today, today
    elif period == 'week':
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == 'month':
        start = today.replace(day=1)
        return start, today
    elif period == 'year':
        start = today.replace(month=1, day=1)
        return start, today
    return today.replace(day=1), today
