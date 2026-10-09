from extensions import db
from datetime import datetime

class Quotation(db.Model):
    __tablename__ = 'quotations'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    quotation_no = db.Column(db.String(50), nullable=False)
    quotation_date = db.Column(db.Date, nullable=False)
    valid_till = db.Column(db.Date)
    is_igst = db.Column(db.Boolean, default=False)
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    total_discount = db.Column(db.Numeric(15, 2), default=0)
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    grand_total = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default='draft')  # draft/sent/accepted/rejected/converted
    converted_invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    items = db.relationship('QuotationItem', backref='quotation', lazy='dynamic', cascade='all, delete-orphan')
    customer = db.relationship('Customer', foreign_keys=[customer_id])

    def __repr__(self):
        return f'<Quotation {self.quotation_no}>'


class QuotationItem(db.Model):
    __tablename__ = 'quotation_items'

    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    description = db.Column(db.String(500), nullable=False)
    hsn_sac = db.Column(db.String(20))
    qty = db.Column(db.Numeric(10, 3), default=1)
    unit = db.Column(db.String(20))
    rate = db.Column(db.Numeric(15, 2), default=0)
    discount_pct = db.Column(db.Numeric(5, 2), default=0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0)
    amount = db.Column(db.Numeric(15, 2), default=0)
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    gst_rate = db.Column(db.Numeric(5, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    sort_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<QuotationItem {self.description}>'
