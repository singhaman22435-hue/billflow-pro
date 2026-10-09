from extensions import db
from datetime import datetime

class Vendor(db.Model):
    __tablename__ = 'vendors'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(200))
    company_name = db.Column(db.String(200))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    gstin = db.Column(db.String(20))
    pan = db.Column(db.String(20))
    state_code = db.Column(db.String(5))
    state = db.Column(db.String(100))
    address = db.Column(db.String(300))
    city = db.Column(db.String(100))
    pincode = db.Column(db.String(10))
    opening_balance = db.Column(db.Numeric(15, 2), default=0)
    payment_terms = db.Column(db.Integer, default=30)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Vendor {self.name}>'
