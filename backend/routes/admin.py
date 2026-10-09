from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models.organization import Organization
from models.user import User
from models.subscription import Subscription
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
def require_super_admin():
    # Allow the setup route to bypass the super_admin check
    if request.endpoint == 'admin.setup_super_admin':
        return
    if not current_user.is_super_admin:
        flash('Access denied. Super Admin only.', 'danger')
        return redirect(url_for('dashboard.index'))

@admin_bp.route('/setup-super-admin')
@login_required
def setup_super_admin():
    # This route makes the current user a super admin (one-time backdoor for the creator)
    if not current_user.is_super_admin:
        user = User.query.get(current_user.id)
        user.is_super_admin = True
        db.session.commit()
        flash('You are now a Super Admin!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/dashboard')
def dashboard():
    total_orgs = Organization.query.count()
    total_users = User.query.count()
    total_revenue = db.session.query(db.func.sum(Subscription.amount)).filter(Subscription.status == 'paid').scalar() or 0
    active_subs = Subscription.query.filter_by(status='paid').count()

    from models.invoice import Invoice
    total_invoices = Invoice.query.count()
    total_invoiced_amount = db.session.query(db.func.sum(Invoice.grand_total)).scalar() or 0

    recent_orgs = Organization.query.order_by(Organization.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html', 
                           total_orgs=total_orgs, 
                           total_users=total_users, 
                           total_revenue=total_revenue,
                           active_subs=active_subs,
                           total_invoices=total_invoices,
                           total_invoiced_amount=total_invoiced_amount,
                           recent_orgs=recent_orgs)

@admin_bp.route('/users')
def users():
    search = request.args.get('q', '')
    query = User.query
    if search:
        query = query.filter(User.name.ilike(f'%{search}%') | User.email.ilike(f'%{search}%'))
    users_list = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users_list, search=search)

@admin_bp.route('/organizations')
def organizations():
    search = request.args.get('q', '')
    query = Organization.query
    if search:
        query = query.filter(Organization.name.ilike(f'%{search}%'))
    orgs = query.order_by(Organization.created_at.desc()).all()
    return render_template('admin/organizations.html', orgs=orgs, search=search)

@admin_bp.route('/organizations/<int:id>/update_plan', methods=['POST'])
def update_plan(id):
    org = Organization.query.get_or_404(id)
    plan = request.form.get('plan')
    is_active = request.form.get('is_active') == 'true'
    
    org.plan = plan
    org.is_active = is_active
    db.session.commit()
    
    flash(f"Organization {org.name} updated successfully.", 'success')
    return redirect(url_for('admin.organizations'))

@admin_bp.route('/subscriptions')
def subscriptions():
    status = request.args.get('status', 'pending_approval')
    subs = Subscription.query.filter_by(payment_method='manual_upi', status=status).order_by(Subscription.created_at.desc()).all()
    return render_template('admin/subscriptions.html', subscriptions=subs, status=status)

@admin_bp.route('/subscriptions/<int:id>/approve', methods=['POST'])
def approve_subscription(id):
    from routes.subscription import PLANS
    from dateutil.relativedelta import relativedelta
    
    sub = Subscription.query.get_or_404(id)
    if sub.status != 'pending_approval':
        flash('Subscription is not pending.', 'warning')
        return redirect(url_for('admin.subscriptions'))
        
    sub.status = 'paid'
    sub.paid_at = datetime.utcnow()
    
    # Update Org
    plan = PLANS.get(sub.plan_name)
    if plan:
        org = sub.organization
        org.plan = plan['name'].lower()
        now = datetime.utcnow()
        if org.subscription_end and org.subscription_end > now:
            org.subscription_end = org.subscription_end + relativedelta(months=plan['months'])
        else:
            org.subscription_end = now + relativedelta(months=plan['months'])
            
    db.session.commit()
    flash(f"Subscription {id} approved!", 'success')
    return redirect(url_for('admin.subscriptions'))

@admin_bp.route('/subscriptions/<int:id>/reject', methods=['POST'])
def reject_subscription(id):
    sub = Subscription.query.get_or_404(id)
    if sub.status != 'pending_approval':
        flash('Subscription is not pending.', 'warning')
        return redirect(url_for('admin.subscriptions'))
        
    sub.status = 'failed'
    db.session.commit()
    flash(f"Subscription {id} rejected.", 'danger')
    return redirect(url_for('admin.subscriptions'))
