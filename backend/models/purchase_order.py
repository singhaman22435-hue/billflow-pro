from extensions import db
from datetime import datetime

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    po_no = db.Column(db.String(50), nullable=False)
    po_date = db.Column(db.Date, nullable=False)
    delivery_date = db.Column(db.Date)
    delivery_address = db.Column(db.String(300))
    is_igst = db.Column(db.Boolean, default=False)
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    total_discount = db.Column(db.Numeric(15, 2), default=0)
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    grand_total = db.Column(db.Numeric(15, 2), default=0)
    # draft/sent/received/cancelled
    status = db.Column(db.String(20), default='draft')
    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vendor = db.relationship('Vendor', foreign_keys=[vendor_id])
    items = db.relationship('POItem', backref='purchase_order', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<PurchaseOrder {self.po_no}>'


class POItem(db.Model):
    __tablename__ = 'po_items'

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
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
        return f'<POItem {self.description}>'
