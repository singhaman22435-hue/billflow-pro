from flask import Blueprint, render_template
from flask_login import login_required, current_user
from extensions import db, cache
from models.invoice import Invoice
from models.customer import Customer
from models.payment import Payment
from sqlalchemy import func
from datetime import datetime, date, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

def cache_key():
    return f"dashboard_{current_user.org_id}"

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
@cache.cached(timeout=300, key_prefix=cache_key)
def index():
    org_id = current_user.org_id
    today = date.today()
    month_start = today.replace(day=1)

    # KPIs
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.org_id == org_id
    ).scalar() or 0

    monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.org_id == org_id,
        Payment.payment_date >= month_start
    ).scalar() or 0

    outstanding = db.session.query(func.sum(Invoice.balance_due)).filter(
        Invoice.org_id == org_id,
        Invoice.status.in_(['sent', 'partial'])
    ).scalar() or 0

    overdue = db.session.query(func.sum(Invoice.balance_due)).filter(
        Invoice.org_id == org_id,
        Invoice.status.in_(['sent', 'partial']),
        Invoice.due_date < today
    ).scalar() or 0

    total_invoices = Invoice.query.filter_by(org_id=org_id).count()
    total_customers = Customer.query.filter_by(org_id=org_id, is_active=True).count()

    # Recent Invoices
    from sqlalchemy.orm import joinedload
    recent_invoices = Invoice.query.options(joinedload(Invoice.customer)).filter_by(org_id=org_id).order_by(
        Invoice.created_at.desc()
    ).limit(8).all()

    # Monthly revenue for last 6 months (chart data)
    monthly_data = []
    for i in range(5, -1, -1):
        d = today.replace(day=1) - timedelta(days=i*30)
        m_start = d.replace(day=1)
        if d.month == 12:
            m_end = d.replace(year=d.year+1, month=1, day=1)
        else:
            m_end = d.replace(month=d.month+1, day=1)
        
        rev = db.session.query(func.sum(Payment.amount)).filter(
            Payment.org_id == org_id,
            Payment.payment_date >= m_start,
            Payment.payment_date < m_end
        ).scalar() or 0
        
        inv_count = Invoice.query.filter(
            Invoice.org_id == org_id,
            Invoice.invoice_date >= m_start,
            Invoice.invoice_date < m_end
        ).count()
        
        monthly_data.append({
            'month': m_start.strftime('%b %Y'),
            'revenue': float(rev),
            'invoice_count': inv_count
        })

    # Top customers
    top_customers = db.session.query(
        Customer.name,
        func.sum(Invoice.grand_total).label('total')
    ).join(Invoice, Invoice.customer_id == Customer.id).filter(
        Invoice.org_id == org_id
    ).group_by(Customer.id, Customer.name).order_by(
        func.sum(Invoice.grand_total).desc()
    ).limit(5).all()

    # Low Stock Alerts
    from models.item import Item
    low_stock_items = Item.query.filter_by(
        org_id=org_id, is_active=True, track_inventory=True
    ).all()
    low_stock_alerts = [i for i in low_stock_items if i.is_low_stock]

    # Recurring invoices due
    from models.recurring_invoice import RecurringInvoice
    recurring_due = RecurringInvoice.query.filter_by(
        org_id=org_id, is_active=True
    ).filter(RecurringInvoice.next_date <= today).count()

    return render_template('dashboard/index.html',
        total_revenue=float(total_revenue),
        monthly_revenue=float(monthly_revenue),
        outstanding=float(outstanding),
        overdue=float(overdue),
        total_invoices=total_invoices,
        total_customers=total_customers,
        recent_invoices=recent_invoices,
        monthly_data=monthly_data,
        top_customers=top_customers,
        low_stock_alerts=low_stock_alerts,
        recurring_due=recurring_due,
        today=today
    )

