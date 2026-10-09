from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models.user import User, AuditLog
from models.organization import Organization
from datetime import datetime

auth_bp = Blueprint('auth', __name__)


def get_client_ip():
    """Get real client IP, even behind proxy/Render"""
    x_forwarded = request.headers.get('X-Forwarded-For')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.remote_addr


# ─── REGISTER ─────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validations
        if not all([company_name, name, email, password]):
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        # Strong password validation
        is_valid, msg = User.validate_password_strength(password)
        if not is_valid:
            flash(msg, 'danger')
            return render_template('auth/register.html')

        # Fake/Temp Email Validation
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email format.', 'danger')
            return render_template('auth/register.html')
            
        try:
            from disposable_email_domains import blocklist
            domain = email.split('@')[-1].lower()
            if domain in blocklist:
                flash('Please use a real business or personal email. Disposable emails are not allowed.', 'danger')
                return render_template('auth/register.html')
        except ImportError:
            pass

        # Check if email exists
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('An account with this email already exists.', 'danger')
            return render_template('auth/register.html')

        # Create Organization
        org = Organization(
            name=company_name,
            invoice_prefix='INV',
            invoice_start_no=1,
            plan='free'
        )
        db.session.add(org)
        db.session.flush()

        # Create Owner User
        user = User(
            org_id=org.id,
            name=name,
            email=email,
            role='owner'
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        AuditLog.log('register', resource=email, org_id=org.id, user_id=user.id)
        db.session.commit()

        login_user(user, remember=True)
        session.permanent = True
        flash(f'Welcome to BillFlow Pro! Let\'s set up {company_name}.', 'success')
        return redirect(url_for('settings.company_setup'))

    return render_template('auth/register.html')


# ─── LOGIN ────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        ip = get_client_ip()

        user = User.query.filter_by(email=email).first()

        # ── Account Lockout Check ───────────────────────
        try:
            if user and user.is_locked:
                remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
                flash(f'🔒 Account locked due to too many failed attempts. Try again in {remaining} minute(s).', 'danger')
                try:
                    AuditLog.log('login_blocked', resource=email, status='failure',
                                 details=f'Locked. IP: {ip}', org_id=user.org_id)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return render_template('auth/login.html')
        except Exception:
            pass  # locked_until column may not exist yet — skip lockout check

        if user and user.is_active and user.check_password(password):
            # ✅ Successful login
            try:
                user.reset_failed_logins()
                user.last_login = datetime.utcnow()
                user.last_login_ip = ip
                AuditLog.log('login_success', resource=email, org_id=user.org_id, user_id=user.id,
                             details=f'IP: {ip}')
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                    user.last_login = datetime.utcnow()
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            login_user(user, remember=True)
            session.permanent = True
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            # ❌ Failed login
            if user:
                try:
                    user.record_failed_login()
                    failed = user.failed_login_count
                    AuditLog.log('login_failed', resource=email, status='failure',
                                 details=f'Attempt #{failed}. IP: {ip}', org_id=user.org_id)
                    db.session.commit()
                    if user.is_locked:
                        flash('🔒 Too many failed attempts. Account locked for 15 minutes.', 'danger')
                    else:
                        remaining_attempts = max(0, 5 - failed)
                        flash(f'Invalid email or password. {remaining_attempts} attempt(s) remaining before lockout.', 'danger')
                except Exception:
                    db.session.rollback()
                    flash('Invalid email or password.', 'danger')
            else:
                flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


# ─── LOGOUT ───────────────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    AuditLog.log('logout', org_id=current_user.org_id, user_id=current_user.id)
    db.session.commit()
    session.clear()
    logout_user()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('auth.login'))


# ─── FORGOT PASSWORD ──────────────────────────────────────
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        # Always show same message (prevent user enumeration)
        flash('If this email exists, a password reset link has been sent. Check your inbox.', 'info')

        if user:
            token = user.generate_reset_token()
            AuditLog.log('password_reset_request', resource=email,
                         org_id=user.org_id, user_id=user.id)
            db.session.commit()

            # Send email
            try:
                from flask_mail import Message
                from extensions import mail
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                msg = Message(
                    subject='🔐 BillFlow Pro — Password Reset Request',
                    sender='BillFlow Pro <noreply@billflowpro.com>',
                    recipients=[email]
                )
                msg.body = f"""Hi {user.name},

You requested a password reset for your BillFlow Pro account.

Click this link to reset your password (valid for 1 hour):
{reset_url}

If you did NOT request this, please ignore this email. Your account is safe.

— BillFlow Pro Security Team
"""
                mail.send(msg)
            except Exception:
                pass  # Silently fail if mail not configured

    return render_template('auth/forgot_password.html')


# ─── RESET PASSWORD ───────────────────────────────────────
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()

    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        flash('Invalid or expired reset link. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        is_valid, msg = User.validate_password_strength(password)
        if not is_valid:
            flash(msg, 'danger')
            return render_template('auth/reset_password.html', token=token)

        user.set_password(password)
        user.reset_token = None
        user.reset_token_expiry = None
        user.reset_failed_logins()  # Clear any lockouts too
        AuditLog.log('password_reset_success', resource=user.email,
                     org_id=user.org_id, user_id=user.id)
        db.session.commit()

        flash('✅ Password reset successfully! You can now login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


# ─── GOOGLE OAUTH ─────────────────────────────────────────
@auth_bp.route('/login/google')
def google_login():
    try:
        from extensions import oauth
        if oauth is None:
            flash('Google Login is not configured.', 'danger')
            return redirect(url_for('auth.login'))
        google_client = oauth.create_client('google')
        redirect_uri = url_for('auth.google_authorize', _external=True)
        # Force HTTPS - Render proxy strips SSL so Flask generates http:// URLs
        if redirect_uri.startswith('http://'):
            redirect_uri = 'https://' + redirect_uri[7:]
        return google_client.authorize_redirect(redirect_uri)
    except Exception as e:
        flash(f'Google Login failed. Please use Email/Password login. ({str(e)[:80]})', 'danger')
        return redirect(url_for('auth.login'))


@auth_bp.route('/login/google/callback')
def google_authorize():
    try:
        import urllib.request
        import urllib.parse
        import json as json_lib
        from flask import request as flask_req, current_app

        code = flask_req.args.get('code')
        if not code:
            flash('Google login was cancelled.', 'warning')
            return redirect(url_for('auth.login'))

        # Use urllib (gevent-safe) instead of requests to avoid SSL recursion bug
        # gevent + requests SSL = recursive SSLContext.verify_mode.__set__ issue
        redirect_uri = url_for('auth.google_authorize', _external=True)
        # Force HTTPS - Render proxy strips SSL so Flask generates http:// URLs
        if redirect_uri.startswith('http://'):
            redirect_uri = 'https://' + redirect_uri[7:]

        # Step 1: Exchange authorization code for access token
        # Use app.config values (may be Render env vars, not hardcoded fallbacks!)
        client_id = current_app.config.get('GOOGLE_CLIENT_ID')
        client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
        post_data = urllib.parse.urlencode({
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }).encode('utf-8')

        token_req = urllib.request.Request(
            'https://oauth2.googleapis.com/token',
            data=post_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        with urllib.request.urlopen(token_req, timeout=15) as resp:
            token_data = json_lib.loads(resp.read().decode('utf-8'))

        access_token = token_data.get('access_token')
        if not access_token:
            flash('Google login failed: Could not get access token.', 'danger')
            return redirect(url_for('auth.login'))

        # Step 2: Fetch user profile from Google
        userinfo_req = urllib.request.Request(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        with urllib.request.urlopen(userinfo_req, timeout=15) as resp:
            user_info = json_lib.loads(resp.read().decode('utf-8'))

        if not user_info or not user_info.get('email'):
            flash('Could not retrieve email from Google. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        email = user_info.get('email', '').lower()
        name = user_info.get('name') or email.split('@')[0]
        ip = get_client_ip()

        user = User.query.filter_by(email=email).first()
        if not user:
            org = Organization(name=f"{name}'s Company")
            db.session.add(org)
            db.session.flush()

            user = User(
                org_id=org.id,
                name=name,
                email=email,
                role='owner'
            )
            import secrets
            user.set_password(secrets.token_hex(32))  # Random unusable password
            db.session.add(user)
            db.session.flush()

            try:
                AuditLog.log('google_register', resource=email, org_id=org.id, user_id=user.id,
                             details=f'IP: {ip}')
                db.session.commit()
            except Exception:
                db.session.rollback()

            login_user(user, remember=True)
            session.permanent = True
            flash('Account created successfully via Google! Please set up your company.', 'success')
            return redirect(url_for('settings.setup'))
        else:
            try:
                user.last_login = datetime.utcnow()
                user.last_login_ip = ip
                user.reset_failed_logins()
                AuditLog.log('google_login', resource=email, org_id=user.org_id, user_id=user.id,
                             details=f'IP: {ip}')
                db.session.commit()
            except Exception:
                db.session.rollback()

            login_user(user, remember=True)
            session.permanent = True
            flash('Logged in successfully with Google.', 'success')
            return redirect(url_for('dashboard.index'))

    except Exception as e:
        flash(f'Google Login error: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))
