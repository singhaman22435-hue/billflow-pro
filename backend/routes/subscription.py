from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.subscription import Subscription
from models.organization import Organization
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import uuid
import hashlib
import base64
import json
import requests

subscription_bp = Blueprint('subscription', __name__)

PLANS = {
    'basic_monthly': {'name': 'Basic', 'amount': 499, 'months': 1, 'invoice_limit': 500},
    'basic_yearly': {'name': 'Basic', 'amount': 4999, 'months': 12, 'invoice_limit': 500},
    'pro_monthly': {'name': 'Pro', 'amount': 999, 'months': 1, 'invoice_limit': -1},
    'pro_yearly': {'name': 'Pro', 'amount': 9999, 'months': 12, 'invoice_limit': -1},
}

@subscription_bp.route('/subscription/pricing')
@login_required
def pricing():
    return render_template('subscription/pricing.html', plans=PLANS, current_plan=current_user.organization.plan)

@subscription_bp.route('/subscription/checkout/<plan_id>', methods=['GET'])
@login_required
def checkout_page(plan_id):
    if plan_id not in PLANS:
        flash('Invalid plan selected.', 'danger')
        return redirect(url_for('subscription.pricing'))
    plan = PLANS[plan_id]
    upi_id = "8766083129@ptyes" # Configuration
    return render_template('subscription/checkout.html', plan=plan, plan_id=plan_id, upi_id=upi_id)

@subscription_bp.route('/subscription/pay/upi/<plan_id>', methods=['POST'])
@login_required
def pay_manual_upi(plan_id):
    if plan_id not in PLANS:
        flash('Invalid plan.', 'danger')
        return redirect(url_for('subscription.pricing'))
        
    utr_number = request.form.get('utr_number', '').strip()
    import re
    if not utr_number or not re.match(r'^[a-zA-Z0-9]{4,30}$', utr_number):
        flash('Invalid UTR Number.', 'danger')
        return redirect(url_for('subscription.checkout_page', plan_id=plan_id))
        
    plan = PLANS[plan_id]
    
    screenshot = request.files.get('screenshot')
    screenshot_url = None
    if screenshot and screenshot.filename:
        # SECURITY PATCH: Check extension
        ext = screenshot.filename.rsplit('.', 1)[-1].lower()
        if ext not in ['jpg', 'jpeg', 'png']:
            flash('Invalid file type. Only JPG/PNG allowed.', 'danger')
            return redirect(url_for('subscription.checkout_page', plan_id=plan_id))
            
        uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        filename = f"upi_{uuid.uuid4().hex}.{ext}"
        screenshot.save(os.path.join(uploads_dir, filename))
        screenshot_url = f"/static/uploads/{filename}"
    
    sub = Subscription(
        org_id=current_user.organization.id,
        plan_name=plan_id,
        amount=plan['amount'],
        payment_method='manual_upi',
        payment_reference_id=utr_number,
        upi_screenshot_url=screenshot_url,
        status='pending_approval'
    )
    db.session.add(sub)
    
    try:
        db.session.commit()
    except Exception as e:
        import traceback
        db.session.rollback()
        # Handle duplicate UTR
        if 'UNIQUE constraint failed' in str(e) or 'duplicate key value' in str(e):
            flash("This UTR number has already been submitted.", "danger")
        else:
            flash(f"System Error: {traceback.format_exc()}", "danger")
        return redirect(url_for('subscription.checkout_page', plan_id=plan_id))
    
    flash("Payment submitted! Please wait for Admin approval.", "success")
    return redirect(url_for('dashboard.index'))
