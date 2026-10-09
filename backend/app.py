import os
import sys

# Add backend folder to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template
from config import config
from extensions import db, login_manager, mail, migrate, csrf, cache

def create_app(config_name=None):
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(
        __name__,
        template_folder='../frontend/templates',
        static_folder='../frontend/static'
    )
    app.config.from_object(config[config_name])

    # Fix URL generation behind Render's reverse proxy (forces https:// in url_for)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config['PREFERRED_URL_SCHEME'] = 'https'

    from extensions import db, login_manager, mail, migrate, csrf, cache, oauth

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    cache.init_app(app)
    
    # APScheduler has been moved to worker.py to support multi-worker setups
    try:
        from flask_compress import Compress
        Compress(app)
    except ImportError:
        pass
    if oauth:
        oauth.init_app(app)
        oauth.register(
            name='google',
            client_id=app.config.get('GOOGLE_CLIENT_ID'),
            client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
            # Explicit endpoints instead of server_metadata_url to avoid authlib recursion bug
            access_token_url='https://oauth2.googleapis.com/token',
            authorize_url='https://accounts.google.com/o/oauth2/auth',
            jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
            userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
            client_kwargs={
                'scope': 'openid email profile',
                'token_endpoint_auth_method': 'client_secret_post',
            }
        )

    # Login manager settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # Register blueprints
    # Import all models to ensure db.create_all() creates their tables
    from models.recurring_invoice import RecurringInvoice, RecurringInvoiceItem  # noqa
    from models.user import AuditLog  # noqa
    from models.payroll import Employee, Payslip  # noqa
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.customers import customers_bp
    from routes.vendors import vendors_bp
    from routes.items import items_bp
    from routes.invoices import invoices_bp
    from routes.quotations import quotations_bp
    from routes.purchase_orders import po_bp
    from routes.expenses import expenses_bp
    from routes.delivery_challans import dc_bp
    from routes.settings import settings_bp
    from routes.reports import reports_bp
    from routes.subscription import subscription_bp
    from routes.admin import admin_bp
    from routes.recurring import recurring_bp
    from routes.inventory import inventory_bp
    from routes.einvoice import einvoice_bp
    from routes.payroll import payroll_bp
    from routes.bank_recon import bank_recon_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(vendors_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(quotations_bp)
    app.register_blueprint(po_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(dc_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(recurring_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(einvoice_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(bank_recon_bp)

    # Landing page
    @app.route('/home')
    def landing():
        return render_template('landing.html')

    # ─── CUSTOMER PORTAL (public, no login required) ─────────
    @app.route('/portal/<token>')
    def customer_portal(token):
        from models.customer import Customer
        from models.invoice import Invoice
        from models.organization import Organization
        customer = Customer.query.filter_by(portal_token=token).first_or_404()
        org = Organization.query.get(customer.org_id)
        invoices = Invoice.query.filter_by(customer_id=customer.id).order_by(Invoice.invoice_date.desc()).all()
        outstanding = sum(float(i.balance_due) for i in invoices if i.status in ['sent', 'partial'])
        total_paid = sum(float(i.amount_paid) for i in invoices)
        return render_template('portal/customer.html',
            customer=customer, org=org, invoices=invoices,
            outstanding=outstanding, total_paid=total_paid)
        
    @app.route('/debug/db')
    def debug_db():
        import traceback
        try:
            from models.organization import Organization
            org = Organization.query.first()
            return f"Success! Org name: {org.name if org else 'No Org'}"
        except Exception as e:
            return f"<pre>{traceback.format_exc()}</pre>"

    # ─── ERROR HANDLERS ──────────────────────────────────────

    # ── Security Headers (after every response) ──────────────
    @app.after_request
    def add_security_headers(response):
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        # Prevent MIME sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # XSS protection (legacy browsers)
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # HSTS — force HTTPS for 1 year (Render always uses HTTPS)
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Permissions policy — disable sensitive APIs
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        # Content Security Policy
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob: https://api.qrserver.com https://lh3.googleusercontent.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        # Remove server fingerprint
        response.headers.pop('Server', None)
        response.headers.pop('X-Powered-By', None)
        return response

    # PWA Service Worker — must be served from root
    import os as _os
    from flask import send_from_directory as _send_file, Response as _Response
    
    @app.route('/sw.js')
    def service_worker():
        static_dir = _os.path.join(app.root_path, '..', 'frontend', 'static')
        return _send_file(static_dir, 'sw.js', mimetype='application/javascript')

    @app.route('/manifest.json')
    def manifest():
        static_dir = _os.path.join(app.root_path, '..', 'frontend', 'static')
        return _send_file(static_dir, 'manifest.json', mimetype='application/manifest+json')

    @app.route('/static/images/<path:filename>')
    def serve_icon(filename):
        static_dir = _os.path.join(app.root_path, '..', 'frontend', 'static', 'images')
        filepath = _os.path.join(static_dir, filename)
        if _os.path.exists(filepath):
            return _send_file(static_dir, filename)
        # SVG fallback icon if PNG not yet uploaded
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
          <rect width="512" height="512" rx="80" fill="#0a1628"/>
          <rect width="512" height="512" rx="80" fill="url(#g)"/>
          <defs>
            <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#6366f1" stop-opacity="0.15"/>
              <stop offset="100%" stop-color="#8b5cf6" stop-opacity="0.05"/>
            </linearGradient>
          </defs>
          <text x="50%" y="56%" dominant-baseline="middle" text-anchor="middle" 
                font-family="Arial,sans-serif" font-size="260" font-weight="900" fill="url(#t)">B</text>
          <defs>
            <linearGradient id="t" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#a5b4fc"/>
              <stop offset="100%" stop-color="#6366f1"/>
            </linearGradient>
          </defs>
          <rect x="156" y="340" width="200" height="8" rx="4" fill="#6366f1" opacity="0.7"/>
          <rect x="156" y="362" width="150" height="8" rx="4" fill="#6366f1" opacity="0.5"/>
          <rect x="156" y="384" width="120" height="8" rx="4" fill="#6366f1" opacity="0.3"/>
        </svg>'''
        return _Response(svg, mimetype='image/svg+xml')

    # --- LOGIN BYPASS (Auto-Login) ---
    @app.before_request
    def auto_login():
        from flask_login import current_user, login_user
        from models.user import User
        from models.organization import Organization
        from extensions import db
        from flask import request as flask_request, redirect, url_for
        
        # If user visits login pages, redirect them to dashboard
        if flask_request.path.startswith('/login') or flask_request.path.startswith('/register'):
            return redirect(url_for('dashboard.index'))
            
        if not current_user.is_authenticated and not flask_request.path.startswith('/static'):
            user = User.query.filter_by(email='admin@billflow.local').first()
            if not user:
                org = Organization.query.first()
                if not org:
                    org = Organization(name='My Company')
                    db.session.add(org)
                    db.session.commit()
                
                user = User(
                    email='admin@billflow.local',
                    name='Admin User',
                    role='admin',
                    org_id=org.id,
                    is_active=True
                )
                user.set_password('password')
                db.session.add(user)
                db.session.commit()
            
            login_user(user)
    # ---------------------------------

    # Template globals
    from utils.gst_calculator import format_currency, INDIAN_STATES
    app.jinja_env.globals.update(
        format_currency=format_currency,
        INDIAN_STATES=INDIAN_STATES
    )

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        import traceback
        import html
        error_trace = html.escape(traceback.format_exc())
        error_msg = html.escape(str(e))
        return f"<h1>Internal Server Error</h1><pre>{error_msg}</pre><pre style='color:red;'>{error_trace}</pre>", 500

    # Create tables + safe column migrations on every deploy
    # with app.app_context():
    #     db.create_all()
    #     _safe_migrate(db)

    return app


def _safe_migrate(db):
    """
    Add new columns to existing tables without breaking the app.
    Uses standard ALTER TABLE ... ADD COLUMN (compatible with SQLite).
    Safe to run on every startup — won't fail if columns already exist.
    """
    migrations = [
        # ── users table ──────────────────────────────────────────
        "ALTER TABLE users ADD COLUMN last_login_ip VARCHAR(45)",
        "ALTER TABLE users ADD COLUMN failed_login_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN locked_until TIMESTAMP",
        "ALTER TABLE users ADD COLUMN otp_code VARCHAR(10)",
        "ALTER TABLE users ADD COLUMN otp_expiry TIMESTAMP",
        "ALTER TABLE users ADD COLUMN reset_token VARCHAR(128)",
        "ALTER TABLE users ADD COLUMN reset_token_expiry TIMESTAMP",
        "ALTER TABLE users ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE",

        # ── customers table ───────────────────────────────────────
        "ALTER TABLE customers ADD COLUMN company_name VARCHAR(200)",
        "ALTER TABLE customers ADD COLUMN state_code VARCHAR(5)",
        "ALTER TABLE customers ADD COLUMN opening_balance NUMERIC(15,2) DEFAULT 0",
        "ALTER TABLE customers ADD COLUMN payment_terms INTEGER DEFAULT 30",
        "ALTER TABLE customers ADD COLUMN portal_token VARCHAR(64)",

        # ── vendors table ─────────────────────────────────────────
        "ALTER TABLE vendors ADD COLUMN display_name VARCHAR(200)",
        "ALTER TABLE vendors ADD COLUMN company_name VARCHAR(200)",
        "ALTER TABLE vendors ADD COLUMN email VARCHAR(120)",
        "ALTER TABLE vendors ADD COLUMN phone VARCHAR(20)",
        "ALTER TABLE vendors ADD COLUMN gstin VARCHAR(20)",
        "ALTER TABLE vendors ADD COLUMN pan VARCHAR(20)",
        "ALTER TABLE vendors ADD COLUMN state_code VARCHAR(5)",
        "ALTER TABLE vendors ADD COLUMN state VARCHAR(100)",
        "ALTER TABLE vendors ADD COLUMN address VARCHAR(300)",
        "ALTER TABLE vendors ADD COLUMN city VARCHAR(100)",
        "ALTER TABLE vendors ADD COLUMN pincode VARCHAR(10)",
        "ALTER TABLE vendors ADD COLUMN opening_balance NUMERIC(15,2) DEFAULT 0",
        "ALTER TABLE vendors ADD COLUMN payment_terms INTEGER DEFAULT 30",
        "ALTER TABLE vendors ADD COLUMN notes TEXT",
        "ALTER TABLE vendors ADD COLUMN is_active BOOLEAN DEFAULT TRUE",

        # ── items table ───────────────────────────────────────────
        "ALTER TABLE items ADD COLUMN description TEXT",
        "ALTER TABLE items ADD COLUMN hsn_sac VARCHAR(20)",
        "ALTER TABLE items ADD COLUMN tax_preference VARCHAR(20)",
        "ALTER TABLE items ADD COLUMN gst_rate NUMERIC(5,2)",
        "ALTER TABLE items ADD COLUMN cess_rate NUMERIC(5,2)",
        "ALTER TABLE items ADD COLUMN purchase_rate NUMERIC(15,2)",
        "ALTER TABLE items ADD COLUMN selling_rate NUMERIC(15,2)",
        "ALTER TABLE items ADD COLUMN unit VARCHAR(20)",
        "ALTER TABLE items ADD COLUMN is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE items ADD COLUMN category VARCHAR(100)",
        "ALTER TABLE items ADD COLUMN track_inventory BOOLEAN DEFAULT FALSE",
        "ALTER TABLE items ADD COLUMN current_stock NUMERIC(10, 2) DEFAULT 0",
        "ALTER TABLE items ADD COLUMN min_stock_level NUMERIC(10, 2) DEFAULT 0",
        "ALTER TABLE items ADD COLUMN max_stock_level NUMERIC(10, 2) DEFAULT 0",
        "ALTER TABLE items ADD COLUMN warehouse_location VARCHAR(100)",

        # ── organizations table ───────────────────────────────────
        "ALTER TABLE organizations ADD COLUMN legal_name VARCHAR(200)",
        "ALTER TABLE organizations ADD COLUMN gstin VARCHAR(20)",
        "ALTER TABLE organizations ADD COLUMN pan VARCHAR(20)",
        "ALTER TABLE organizations ADD COLUMN email VARCHAR(120)",
        "ALTER TABLE organizations ADD COLUMN phone VARCHAR(20)",
        "ALTER TABLE organizations ADD COLUMN address_line1 VARCHAR(200)",
        "ALTER TABLE organizations ADD COLUMN address_line2 VARCHAR(200)",
        "ALTER TABLE organizations ADD COLUMN city VARCHAR(100)",
        "ALTER TABLE organizations ADD COLUMN state VARCHAR(100)",
        "ALTER TABLE organizations ADD COLUMN state_code VARCHAR(5)",
        "ALTER TABLE organizations ADD COLUMN pincode VARCHAR(10)",
        "ALTER TABLE organizations ADD COLUMN country VARCHAR(50) DEFAULT 'India'",
        "ALTER TABLE organizations ADD COLUMN logo_url VARCHAR(500)",
        "ALTER TABLE organizations ALTER COLUMN logo_url TYPE TEXT",
        "ALTER TABLE organizations ADD COLUMN website VARCHAR(200)",
        "ALTER TABLE organizations ADD COLUMN bank_name VARCHAR(100)",
        "ALTER TABLE organizations ADD COLUMN bank_account_no VARCHAR(50)",
        "ALTER TABLE organizations ADD COLUMN bank_ifsc VARCHAR(20)",
        "ALTER TABLE organizations ADD COLUMN bank_branch VARCHAR(100)",
        "ALTER TABLE organizations ADD COLUMN upi_id VARCHAR(100)",
        "ALTER TABLE organizations ADD COLUMN quotation_prefix VARCHAR(20) DEFAULT 'QT'",
        "ALTER TABLE organizations ADD COLUMN po_prefix VARCHAR(20) DEFAULT 'PO'",
        "ALTER TABLE organizations ADD COLUMN default_payment_terms INTEGER DEFAULT 30",
        "ALTER TABLE organizations ADD COLUMN default_notes TEXT",
        "ALTER TABLE organizations ADD COLUMN default_terms TEXT",
        "ALTER TABLE organizations ADD COLUMN currency VARCHAR(10) DEFAULT 'INR'",
        "ALTER TABLE organizations ADD COLUMN financial_year_start VARCHAR(5) DEFAULT '04-01'",
        "ALTER TABLE organizations ADD COLUMN invoice_template VARCHAR(20) DEFAULT 'modern'",
        "ALTER TABLE organizations ADD COLUMN reminder_before_due BOOLEAN DEFAULT TRUE",
        "ALTER TABLE organizations ADD COLUMN reminder_on_due BOOLEAN DEFAULT TRUE",
        "ALTER TABLE organizations ADD COLUMN reminder_after_due BOOLEAN DEFAULT TRUE",
        "ALTER TABLE organizations ADD COLUMN plan VARCHAR(20) DEFAULT 'free'",
        "ALTER TABLE organizations ADD COLUMN invoice_count_this_month INTEGER DEFAULT 0",

        # ── invoices table ────────────────────────────────────────
        "ALTER TABLE invoices ADD COLUMN invoice_type VARCHAR(20) DEFAULT 'tax_invoice'",
        "ALTER TABLE invoices ADD COLUMN place_of_supply VARCHAR(100)",
        "ALTER TABLE invoices ADD COLUMN subtotal NUMERIC(15,2) DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN total_discount NUMERIC(15,2) DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN cess_amount NUMERIC(15,2) DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN round_off NUMERIC(5,2) DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN amount_paid NUMERIC(15,2) DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN balance_due NUMERIC(15,2) DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN last_reminder_sent TIMESTAMP",
        "ALTER TABLE invoices ADD COLUMN tds_applicable BOOLEAN DEFAULT FALSE",
        "ALTER TABLE invoices ADD COLUMN tds_section VARCHAR(20)",
        "ALTER TABLE invoices ADD COLUMN tds_rate NUMERIC(5, 2) DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN tds_amount NUMERIC(15, 2) DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN irn VARCHAR(100)",
        "ALTER TABLE invoices ADD COLUMN ack_no VARCHAR(50)",
        "ALTER TABLE invoices ADD COLUMN ack_date TIMESTAMP",
        "ALTER TABLE invoices ADD COLUMN ewb_no VARCHAR(50)",
        "ALTER TABLE invoices ADD COLUMN qr_code_data TEXT",
        "ALTER TABLE invoices ADD COLUMN recurring_id INTEGER",

        # ── invoice_items table ───────────────────────────────────
        "ALTER TABLE invoice_items ADD COLUMN discount_pct NUMERIC(5,2) DEFAULT 0",
        "ALTER TABLE invoice_items ADD COLUMN discount_amount NUMERIC(15,2) DEFAULT 0",
        "ALTER TABLE invoice_items ADD COLUMN cess_rate NUMERIC(5,2) DEFAULT 0",
        "ALTER TABLE invoice_items ADD COLUMN cess_amount NUMERIC(15,2) DEFAULT 0",
        "ALTER TABLE invoice_items ADD COLUMN unit VARCHAR(20) DEFAULT 'Nos'",
        "ALTER TABLE invoice_items ADD COLUMN sort_order INTEGER DEFAULT 0",

        # ── expenses table ────────────────────────────────────────
        "ALTER TABLE expenses ADD COLUMN vendor_id INTEGER",
        "ALTER TABLE expenses ADD COLUMN is_gst_applicable BOOLEAN DEFAULT FALSE",
        "ALTER TABLE expenses ADD COLUMN gst_amount NUMERIC(15, 2) DEFAULT 0",
        "ALTER TABLE expenses ADD COLUMN payment_mode VARCHAR(30) DEFAULT 'cash'",
        "ALTER TABLE expenses ADD COLUMN reference_no VARCHAR(100)",

        # ── purchase_orders table ─────────────────────────────────
        "ALTER TABLE purchase_orders ADD COLUMN is_igst BOOLEAN DEFAULT FALSE",
        "ALTER TABLE purchase_orders ADD COLUMN delivery_date DATE",
        "ALTER TABLE purchase_orders ADD COLUMN delivery_address VARCHAR(300)",
        
        # ── payments table ────────────────────────────────────────
        "ALTER TABLE payments ADD COLUMN payment_mode VARCHAR(20) DEFAULT 'cash'",
        "ALTER TABLE payments ADD COLUMN reference_no VARCHAR(100)",
        "ALTER TABLE payments ADD COLUMN notes TEXT",
        
        # ── subscriptions table ───────────────────────────────────
        "ALTER TABLE subscriptions ADD COLUMN payment_method VARCHAR(50)",
        "ALTER TABLE subscriptions ADD COLUMN payment_reference_id VARCHAR(100)",
        "ALTER TABLE subscriptions ADD COLUMN upi_screenshot_url VARCHAR(255)",
    ]

    for sql in migrations:
        try:
            db.session.execute(db.text(sql))
            db.session.commit()
        except Exception as e:
            db.session.rollback()


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

