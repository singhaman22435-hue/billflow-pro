from extensions import db
from datetime import datetime

class Organization(db.Model):
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    legal_name = db.Column(db.String(200))
    gstin = db.Column(db.String(20))
    pan = db.Column(db.String(20))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(5))
    pincode = db.Column(db.String(10))
    country = db.Column(db.String(50), default='India')
    logo_url = db.Column(db.Text)
    website = db.Column(db.String(200))

    # Bank Details
    bank_name = db.Column(db.String(100))
    bank_account_no = db.Column(db.String(50))
    bank_ifsc = db.Column(db.String(20))
    bank_branch = db.Column(db.String(100))
    upi_id = db.Column(db.String(100))  # UPI ID for QR code on invoices

    # Invoice Settings
    invoice_prefix = db.Column(db.String(20), default='INV')
    invoice_start_no = db.Column(db.Integer, default=1)
    quotation_prefix = db.Column(db.String(20), default='QT')
    po_prefix = db.Column(db.String(20), default='PO')
    default_payment_terms = db.Column(db.Integer, default=30)  # days
    default_notes = db.Column(db.Text)
    default_terms = db.Column(db.Text)
    currency = db.Column(db.String(10), default='INR')
    financial_year_start = db.Column(db.String(5), default='04-01')
    invoice_template = db.Column(db.String(20), default='modern')  # modern/classic/minimal

    # Payment Reminder Settings
    reminder_before_due = db.Column(db.Boolean, default=True)   # 3 days before due
    reminder_on_due = db.Column(db.Boolean, default=True)        # on due date
    reminder_after_due = db.Column(db.Boolean, default=True)     # 7 days overdue

    # SaaS Plan
    plan = db.Column(db.String(20), default='free')  # free/basic/pro
    invoice_count_this_month = db.Column(db.Integer, default=0)
    subscription_end = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = db.relationship('User', backref='organization', lazy='dynamic')
    customers = db.relationship('Customer', backref='organization', lazy='dynamic')
    vendors = db.relationship('Vendor', backref='organization', lazy='dynamic')
    items = db.relationship('Item', backref='organization', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='organization', lazy='dynamic')
    quotations = db.relationship('Quotation', backref='organization', lazy='dynamic')
    payments = db.relationship('Payment', backref='organization', lazy='dynamic')

    def get_invoice_count(self):
        from models.invoice import Invoice
        return Invoice.query.filter_by(org_id=self.id).count()

    def can_create_invoice(self):
        from models.invoice import Invoice
        from datetime import date
        today = date.today()
        count = Invoice.query.filter(
            Invoice.org_id == self.id,
            db.extract('month', Invoice.invoice_date) == today.month,
            db.extract('year', Invoice.invoice_date) == today.year
        ).count()
        
        if self.plan == 'free':
            return count < 50
        elif self.plan == 'basic':
            return count < 500
        return True

    def __repr__(self):
        return f'<Organization {self.name}>'
