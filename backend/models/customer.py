from extensions import db
from datetime import datetime

class Customer(db.Model):
    __tablename__ = 'customers'
    __table_args__ = (
        db.Index('idx_cust_org_active', 'org_id', 'is_active'),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    display_name = db.Column(db.String(200))
    company_name = db.Column(db.String(200))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    gstin = db.Column(db.String(20))
    pan = db.Column(db.String(20))
    state_code = db.Column(db.String(5))
    state = db.Column(db.String(100))

    # Billing Address
    billing_address = db.Column(db.String(300))
    billing_city = db.Column(db.String(100))
    billing_state = db.Column(db.String(100))
    billing_pincode = db.Column(db.String(10))

    # Shipping Address
    shipping_address = db.Column(db.String(300))
    shipping_city = db.Column(db.String(100))
    shipping_state = db.Column(db.String(100))
    shipping_pincode = db.Column(db.String(10))

    credit_limit = db.Column(db.Numeric(15, 2), default=0)
    opening_balance = db.Column(db.Numeric(15, 2), default=0)
    payment_terms = db.Column(db.Integer, default=30)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    portal_token = db.Column(db.String(64), unique=True)  # Customer self-service portal
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    invoices = db.relationship('Invoice', backref='customer', lazy='dynamic')

    def get_outstanding(self):
        from models.invoice import Invoice
        from sqlalchemy import func
        total = db.session.query(func.sum(Invoice.balance_due)).filter(
            Invoice.customer_id == self.id,
            Invoice.status.in_(['sent', 'partial'])
        ).scalar() or 0
        return float(total)

    def __repr__(self):
        return f'<Customer {self.name}>'
