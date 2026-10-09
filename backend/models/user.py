from extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import re

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='viewer')  # owner/admin/accountant/viewer
    is_active = db.Column(db.Boolean, default=True)
    is_super_admin = db.Column(db.Boolean, default=False)
    profile_pic = db.Column(db.String(500))
    last_login = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))        # IPv6 max length
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Account Lockout (Brute Force Protection) ──────
    failed_login_count = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)            # Null = not locked
    
    # ── Email OTP (2FA) ───────────────────────────────
    otp_code = db.Column(db.String(10))
    otp_expiry = db.Column(db.DateTime)
    
    # ── Password Reset ────────────────────────────────
    reset_token = db.Column(db.String(128))
    reset_token_expiry = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('org_id', 'email', name='uq_user_org_email'),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256:600000')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_locked(self):
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    def record_failed_login(self):
        self.failed_login_count = (self.failed_login_count or 0) + 1
        if self.failed_login_count >= 5:
            # Lock for 15 minutes after 5 failed attempts
            self.locked_until = datetime.utcnow() + timedelta(minutes=15)

    def reset_failed_logins(self):
        self.failed_login_count = 0
        self.locked_until = None

    def generate_otp(self):
        import secrets
        self.otp_code = str(secrets.randbelow(900000) + 100000)  # 6-digit OTP
        self.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
        return self.otp_code

    def verify_otp(self, code):
        if not self.otp_code or not self.otp_expiry:
            return False
        if datetime.utcnow() > self.otp_expiry:
            return False
        return self.otp_code == str(code)

    def generate_reset_token(self):
        import secrets
        self.reset_token = secrets.token_urlsafe(64)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

    @staticmethod
    def validate_password_strength(password):
        """Returns (is_valid, error_message)"""
        if len(password) < 8:
            return False, 'Password must be at least 8 characters.'
        if not re.search(r'[A-Z]', password):
            return False, 'Password must contain at least one uppercase letter.'
        if not re.search(r'[0-9]', password):
            return False, 'Password must contain at least one number.'
        if not re.search(r'[^A-Za-z0-9]', password):
            return False, 'Password must contain at least one special character (!@#$%...).'
        return True, ''

    def can(self, action):
        """Role-based permission check"""
        permissions = {
            'owner':      ['view', 'create', 'edit', 'delete', 'settings', 'reports'],
            'admin':      ['view', 'create', 'edit', 'delete', 'reports'],
            'accountant': ['view', 'create', 'edit', 'reports'],
            'sales':      ['view', 'create'],
            'viewer':     ['view'],
        }
        return action in permissions.get(self.role, [])

    def __repr__(self):
        return f'<User {self.email}>'


class AuditLog(db.Model):
    """Security audit trail — tracks all important actions"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)   # e.g. "login", "create_invoice"
    resource = db.Column(db.String(100))                  # e.g. "Invoice #INV-2026-0001"
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(300))
    status = db.Column(db.String(20), default='success')  # success/failure/warning
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', foreign_keys=[user_id], backref='audit_logs')

    @classmethod
    def log(cls, action, resource=None, status='success', details=None, org_id=None, user_id=None):
        from flask import request as req
        try:
            entry = cls(
                org_id=org_id,
                user_id=user_id,
                action=action,
                resource=str(resource)[:100] if resource else None,
                ip_address=req.remote_addr,
                user_agent=req.user_agent.string[:300] if req and req.user_agent and req.user_agent.string else None,
                status=status,
                details=str(details)[:500] if details else None,
                timestamp=datetime.utcnow()
            )
            db.session.add(entry)
            # NOTE: Caller must commit. Never commit here to avoid nested transactions.
        except Exception:
            pass  # NEVER let audit logging crash the app


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

