from extensions import db
from datetime import datetime

class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    plan_name = db.Column(db.String(50), nullable=False)  # basic_monthly, basic_yearly, pro_monthly, pro_yearly
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    payment_method = db.Column(db.String(50), nullable=True)  # phonepe, manual_upi
    payment_reference_id = db.Column(db.String(100), unique=True, nullable=True) # Transaction ID or UTR
    upi_screenshot_url = db.Column(db.String(255), nullable=True)
    
    status = db.Column(db.String(20), default='created')  # created, pending_approval, paid, failed
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)

    organization = db.relationship('Organization', backref=db.backref('subscriptions', lazy='dynamic'))

    def __repr__(self):
        return f'<Subscription {self.plan_name} - {self.status}>'
