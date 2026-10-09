from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from extensions import db
from models.organization import Organization
import os
import uuid

settings_bp = Blueprint('settings', __name__)

def org_id():
    return current_user.org_id

@settings_bp.route('/settings/company', methods=['GET', 'POST'])
@login_required
def company():
    org = Organization.query.get_or_404(org_id())
    if not current_user.can('settings'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        try:
            org.name = request.form.get('name')
            org.legal_name = request.form.get('legal_name')
            org.gstin = request.form.get('gstin')
            org.pan = request.form.get('pan')
            org.email = request.form.get('email')
            org.phone = request.form.get('phone')
            org.address_line1 = request.form.get('address_line1')
            org.address_line2 = request.form.get('address_line2')
            org.city = request.form.get('city')
            org.state = request.form.get('state')
            org.state_code = request.form.get('state_code')
            org.pincode = request.form.get('pincode')
            org.website = request.form.get('website')
            org.bank_name = request.form.get('bank_name')
            org.bank_account_no = request.form.get('bank_account_no')
            org.bank_ifsc = request.form.get('bank_ifsc')
            org.bank_branch = request.form.get('bank_branch')
            org.upi_id = request.form.get('upi_id', '')
            org.invoice_prefix = request.form.get('invoice_prefix') or 'INV'
            
            # Safe integer conversion
            try:
                org.invoice_start_no = int(request.form.get('invoice_start_no') or 1)
            except ValueError:
                org.invoice_start_no = 1
                
            try:
                org.default_payment_terms = int(request.form.get('default_payment_terms') or 30)
            except ValueError:
                org.default_payment_terms = 30
                
            org.default_notes = request.form.get('default_notes')
            org.default_terms = request.form.get('default_terms')

            # Logo upload
            logo_file = request.files.get('logo')
            if logo_file and logo_file.filename:
                import base64
                file_bytes = logo_file.read()
                if len(file_bytes) > 2 * 1024 * 1024:  # 2MB limit
                    flash('Logo file too large. Please upload under 2MB.', 'warning')
                else:
                    ext = logo_file.filename.rsplit('.', 1)[-1].lower()
                    mime = 'image/png' if ext == 'png' else 'image/jpeg' if ext in ['jpg','jpeg'] else 'image/webp'
                    b64 = base64.b64encode(file_bytes).decode('utf-8')
                    org.logo_url = f"data:{mime};base64,{b64}"
                    flash('Logo uploaded successfully! ✅', 'success')

            db.session.commit()
            flash('Company settings saved!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'System Error: {str(e)}', 'danger')
            
        return redirect(url_for('settings.company'))

    INDIAN_STATES = [
        ('01', 'Jammu and Kashmir'), ('02', 'Himachal Pradesh'), ('03', 'Punjab'),
        ('04', 'Chandigarh'), ('05', 'Uttarakhand'), ('06', 'Haryana'),
        ('07', 'Delhi'), ('08', 'Rajasthan'), ('09', 'Uttar Pradesh'),
        ('10', 'Bihar'), ('11', 'Sikkim'), ('12', 'Arunachal Pradesh'),
        ('13', 'Nagaland'), ('14', 'Manipur'), ('15', 'Mizoram'),
        ('16', 'Tripura'), ('17', 'Meghalaya'), ('18', 'Assam'),
        ('19', 'West Bengal'), ('20', 'Jharkhand'), ('21', 'Odisha'),
        ('22', 'Chhattisgarh'), ('23', 'Madhya Pradesh'), ('24', 'Gujarat'),
        ('27', 'Maharashtra'), ('29', 'Karnataka'), ('30', 'Goa'),
        ('32', 'Kerala'), ('33', 'Tamil Nadu'), ('34', 'Puducherry'),
        ('36', 'Telangana'), ('37', 'Andhra Pradesh')
    ]

    try:
        from models.invoice import Invoice
        from datetime import date
        today = date.today()
        count_this_month = Invoice.query.filter(
            Invoice.org_id == org.id,
            db.extract('month', Invoice.invoice_date) == today.month,
            db.extract('year', Invoice.invoice_date) == today.year
        ).count()
        org.invoice_count_this_month = count_this_month
    except:
        org.invoice_count_this_month = 0

    return render_template('settings/company.html', org=org, INDIAN_STATES=INDIAN_STATES)

@settings_bp.route('/settings/setup', methods=['GET', 'POST'])
@login_required
def company_setup():
    """Onboarding wizard for new companies"""
    org = Organization.query.get_or_404(org_id())
    return render_template('settings/setup.html', org=org)

# ─── SETUP alias (for Google OAuth redirect) ──────────────
@settings_bp.route('/settings/setup-profile', methods=['GET', 'POST'])
@login_required
def setup():
    return redirect(url_for('settings.company_setup'))

# ─── AUDIT LOG ────────────────────────────────────────────
@settings_bp.route('/settings/audit-log')
@login_required
def audit_log():
    if not current_user.can('settings'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))
    from models.user import AuditLog
    logs = AuditLog.query.filter_by(org_id=org_id())\
        .order_by(AuditLog.timestamp.desc()).limit(200).all()
    return render_template('settings/audit_log.html', logs=logs)

# ─── STAFF MANAGEMENT ────────────────────────────────────
@settings_bp.route('/settings/staff')
@login_required
def staff():
    if not current_user.can('settings'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))
    from models.user import User
    members = User.query.filter_by(org_id=org_id()).order_by(User.created_at).all()
    return render_template('settings/staff.html', staff=members)

@settings_bp.route('/settings/staff/invite', methods=['POST'])
@login_required
def invite_staff():
    if not current_user.can('settings'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))
    from models.user import User, AuditLog
    import secrets

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    role = request.form.get('role', 'viewer')

    if not name or not email:
        flash('Name and email are required.', 'danger')
        return redirect(url_for('settings.staff'))

    import re
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash('Invalid email format.', 'danger')
        return redirect(url_for('settings.staff'))

    try:
        from disposable_email_domains import blocklist
        domain = email.split('@')[-1].lower()
        if domain in blocklist:
            flash('Cannot invite a temporary or disposable email.', 'danger')
            return redirect(url_for('settings.staff'))
    except ImportError:
        pass

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash(f'User with email {email} already exists.', 'danger')
        return redirect(url_for('settings.staff'))

    temp_password = secrets.token_urlsafe(10)
    user = User(
        org_id=org_id(),
        name=name,
        email=email,
        role=role
    )
    user.set_password(temp_password)
    db.session.add(user)

    AuditLog.log('staff_invited', resource=f'{name} ({email})',
                 org_id=org_id(), user_id=current_user.id)
    db.session.commit()

    flash(f'✅ {name} added! Temporary password: {temp_password} — Share this securely.', 'success')
    return redirect(url_for('settings.staff'))

@settings_bp.route('/settings/staff/<int:user_id>/role', methods=['POST'])
@login_required
def change_role(user_id):
    if not current_user.can('settings'):
        flash('Access denied.', 'danger')
        return redirect(url_for('settings.staff'))
    from models.user import User, AuditLog
    member = User.query.filter_by(id=user_id, org_id=org_id()).first_or_404()
    if member.role == 'owner':
        flash('Cannot change owner role.', 'danger')
        return redirect(url_for('settings.staff'))
    new_role = request.form.get('role')
    if new_role in ['admin', 'accountant', 'viewer']:
        member.role = new_role
        AuditLog.log('role_changed', resource=f'{member.email} → {new_role}',
                     org_id=org_id(), user_id=current_user.id)
        db.session.commit()
        flash(f'{member.name} role changed to {new_role}.', 'success')
    return redirect(url_for('settings.staff'))

@settings_bp.route('/settings/staff/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user(user_id):
    if not current_user.can('settings'):
        flash('Access denied.', 'danger')
        return redirect(url_for('settings.staff'))
    from models.user import User, AuditLog
    member = User.query.filter_by(id=user_id, org_id=org_id()).first_or_404()
    if member.role == 'owner' or member.id == current_user.id:
        flash('Cannot deactivate owner or yourself.', 'danger')
        return redirect(url_for('settings.staff'))
    member.is_active = not member.is_active
    AuditLog.log('user_toggled', resource=f'{member.email} → {"active" if member.is_active else "inactive"}',
                 org_id=org_id(), user_id=current_user.id)
    db.session.commit()
    flash(f'{member.name} {"activated" if member.is_active else "deactivated"}.', 'success')
    return redirect(url_for('settings.staff'))

@settings_bp.route('/settings/staff/<int:user_id>/unlock', methods=['POST'])
@login_required
def unlock_user(user_id):
    if not current_user.can('settings'):
        flash('Access denied.', 'danger')
        return redirect(url_for('settings.staff'))
    from models.user import User, AuditLog
    member = User.query.filter_by(id=user_id, org_id=org_id()).first_or_404()
    member.reset_failed_logins()
    AuditLog.log('user_unlocked', resource=member.email, org_id=org_id(), user_id=current_user.id)
    db.session.commit()
    flash(f'{member.name} account unlocked.', 'success')
    return redirect(url_for('settings.staff'))

@settings_bp.route('/settings/staff/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_user(user_id):
    if not current_user.can('settings'):
        flash('Access denied.', 'danger')
        return redirect(url_for('settings.staff'))
    from models.user import User, AuditLog
    member = User.query.filter_by(id=user_id, org_id=org_id()).first_or_404()
    if member.role == 'owner' or member.id == current_user.id:
        flash('Cannot remove owner or yourself.', 'danger')
        return redirect(url_for('settings.staff'))
    name = member.name
    AuditLog.log('user_removed', resource=member.email, org_id=org_id(), user_id=current_user.id)
    db.session.delete(member)
    db.session.commit()
    flash(f'{name} removed from your team.', 'info')
    return redirect(url_for('settings.staff'))

