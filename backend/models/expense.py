from extensions import db
from datetime import datetime

class Expense(db.Model):
    """Manual expenses for P&L (rent, salary, utilities, etc.)"""
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(100), nullable=False)  # Rent, Salary, Utilities, etc.
    description = db.Column(db.String(500))
    amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    payment_mode = db.Column(db.String(30), default='cash')  # cash, bank, upi, cheque
    reference_no = db.Column(db.String(100))
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    is_gst_applicable = db.Column(db.Boolean, default=False)
    gst_amount = db.Column(db.Numeric(15, 2), default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vendor = db.relationship('Vendor', foreign_keys=[vendor_id])

    CATEGORIES = [
        'Rent', 'Salaries & Wages', 'Electricity', 'Internet & Phone',
        'Office Supplies', 'Travel & Conveyance', 'Repairs & Maintenance',
        'Marketing & Advertising', 'Professional Fees', 'Insurance',
        'Bank Charges', 'Miscellaneous', 'Raw Material', 'Other'
    ]

    def __repr__(self):
        return f'<Expense {self.category} {self.amount}>'


class DeliveryChallan(db.Model):
    """Delivery Challan (DC) for goods delivery without invoice"""
    __tablename__ = 'delivery_challans'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)  # linked invoice
    dc_no = db.Column(db.String(50), nullable=False)
    dc_date = db.Column(db.Date, nullable=False)
    dc_type = db.Column(db.String(30), default='delivery')  # delivery, job_work, returnable
    vehicle_no = db.Column(db.String(30))
    driver_name = db.Column(db.String(100))
    delivery_address = db.Column(db.Text)
    notes = db.Column(db.Text)
    # draft/dispatched/delivered/cancelled
    status = db.Column(db.String(20), default='draft')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', foreign_keys=[customer_id])
    invoice = db.relationship('Invoice', foreign_keys=[invoice_id])
    items = db.relationship('DCItem', backref='challan', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<DC {self.dc_no}>'


class DCItem(db.Model):
    __tablename__ = 'dc_items'

    id = db.Column(db.Integer, primary_key=True)
    dc_id = db.Column(db.Integer, db.ForeignKey('delivery_challans.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    description = db.Column(db.String(500), nullable=False)
    hsn_sac = db.Column(db.String(20))
    qty = db.Column(db.Numeric(10, 3), default=1)
    unit = db.Column(db.String(20))
    remarks = db.Column(db.String(200))
    sort_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<DCItem {self.description}>'
