from extensions import db
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

class RecurringInvoice(db.Model):
    __tablename__ = 'recurring_invoices'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    name = db.Column(db.String(200))                  # e.g. "Monthly Hosting Fee"
    
    # Schedule
    frequency = db.Column(db.String(20), default='monthly')  # daily/weekly/monthly/quarterly/yearly
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)                     # None = forever
    next_date = db.Column(db.Date)                    # Next invoice generation date
    last_generated = db.Column(db.Date)
    
    # Invoice Template Data (stored as JSON-ish fields)
    invoice_type = db.Column(db.String(20), default='tax_invoice')
    place_of_supply = db.Column(db.String(100))
    is_igst = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    tds_applicable = db.Column(db.Boolean, default=False)
    tds_section = db.Column(db.String(20))
    tds_rate = db.Column(db.Numeric(5, 2), default=0)
    
    is_active = db.Column(db.Boolean, default=True)
    auto_send_email = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    customer = db.relationship('Customer', foreign_keys=[customer_id])
    items = db.relationship('RecurringInvoiceItem', backref='recurring_invoice',
                            cascade='all, delete-orphan')
    invoices = db.relationship('Invoice', backref='recurring',
                               foreign_keys='Invoice.recurring_id', lazy='dynamic')

    def compute_next_date(self, from_date=None):
        base = from_date or self.next_date or self.start_date
        if self.frequency == 'daily':
            return base + relativedelta(days=1)
        elif self.frequency == 'weekly':
            return base + relativedelta(weeks=1)
        elif self.frequency == 'monthly':
            return base + relativedelta(months=1)
        elif self.frequency == 'quarterly':
            return base + relativedelta(months=3)
        elif self.frequency == 'yearly':
            return base + relativedelta(years=1)
        return base

    @property
    def is_due(self):
        return self.is_active and self.next_date and self.next_date <= date.today()

    def __repr__(self):
        return f'<RecurringInvoice {self.name}>'


class RecurringInvoiceItem(db.Model):
    __tablename__ = 'recurring_invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    recurring_id = db.Column(db.Integer, db.ForeignKey('recurring_invoices.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    description = db.Column(db.String(500))
    hsn_sac = db.Column(db.String(20))
    qty = db.Column(db.Numeric(10, 3), default=1)
    unit = db.Column(db.String(20), default='Nos')
    rate = db.Column(db.Numeric(15, 2), default=0)
    discount_pct = db.Column(db.Numeric(5, 2), default=0)
    gst_rate = db.Column(db.Numeric(5, 2), default=18)
    cess_rate = db.Column(db.Numeric(5, 2), default=0)
    sort_order = db.Column(db.Integer, default=0)

    item = db.relationship('Item', foreign_keys=[item_id])
