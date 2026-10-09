from extensions import db
from datetime import datetime

class Invoice(db.Model):
    __tablename__ = 'invoices'
    __table_args__ = (
        db.Index('idx_inv_org_status', 'org_id', 'status'),
        db.Index('idx_inv_org_date', 'org_id', 'invoice_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    invoice_no = db.Column(db.String(50), nullable=False, index=True)
    invoice_type = db.Column(db.String(20), default='tax_invoice')  # tax_invoice/proforma
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date)
    place_of_supply = db.Column(db.String(100))
    is_igst = db.Column(db.Boolean, default=False)  # interstate = IGST

    # Amounts
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    total_discount = db.Column(db.Numeric(15, 2), default=0)
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    round_off = db.Column(db.Numeric(5, 2), default=0)
    grand_total = db.Column(db.Numeric(15, 2), default=0)
    amount_paid = db.Column(db.Numeric(15, 2), default=0)
    balance_due = db.Column(db.Numeric(15, 2), default=0)

    # Status: draft/sent/partial/paid/cancelled
    status = db.Column(db.String(20), default='draft', index=True)

    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── TDS (Tax Deducted at Source) ─────────────────
    tds_applicable = db.Column(db.Boolean, default=False)
    tds_section = db.Column(db.String(20))     # e.g. "194C", "194J"
    tds_rate = db.Column(db.Numeric(5, 2), default=0)
    tds_amount = db.Column(db.Numeric(15, 2), default=0)

    # ── E-Invoice (IRN) — GST Portal ─────────────────
    irn = db.Column(db.String(100))            # Invoice Reference Number
    ack_no = db.Column(db.String(50))          # Acknowledgement Number
    ack_date = db.Column(db.DateTime)          # Acknowledgement Date
    ewb_no = db.Column(db.String(50))          # E-Way Bill Number
    qr_code_data = db.Column(db.Text)          # QR code string from GSTN

    # ── Recurring Invoice Link ────────────────────────
    recurring_id = db.Column(db.Integer, db.ForeignKey('recurring_invoices.id'), nullable=True)
    last_reminder_sent = db.Column(db.DateTime)  # Payment reminder tracking


    # Relationships
    items = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', lazy='dynamic')

    def calculate_totals(self):
        subtotal = 0
        total_discount = 0
        taxable = 0
        cgst = 0
        sgst = 0
        igst = 0
        cess = 0

        for item in self.items:
            subtotal += float(item.amount)
            total_discount += float(item.discount_amount)
            taxable += float(item.taxable_amount)
            if self.is_igst:
                igst += float(item.igst_amount)
            else:
                cgst += float(item.cgst_amount)
                sgst += float(item.sgst_amount)
            cess += float(item.cess_amount)

        gross = taxable + cgst + sgst + igst + cess
        round_off_val = round(round(gross) - gross, 2)
        grand = round(gross) 

        self.subtotal = subtotal
        self.total_discount = total_discount
        self.taxable_amount = taxable
        self.cgst_amount = cgst
        self.sgst_amount = sgst
        self.igst_amount = igst
        self.cess_amount = cess
        self.round_off = round_off_val
        self.grand_total = grand
        self.balance_due = grand - float(self.amount_paid)

    def __repr__(self):
        return f'<Invoice {self.invoice_no}>'


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    description = db.Column(db.String(500), nullable=False)
    hsn_sac = db.Column(db.String(20))
    qty = db.Column(db.Numeric(10, 3), default=1)
    unit = db.Column(db.String(20))
    rate = db.Column(db.Numeric(15, 2), default=0)
    discount_pct = db.Column(db.Numeric(5, 2), default=0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0)
    amount = db.Column(db.Numeric(15, 2), default=0)         # qty * rate
    taxable_amount = db.Column(db.Numeric(15, 2), default=0) # amount - discount
    gst_rate = db.Column(db.Numeric(5, 2), default=0)
    cgst_rate = db.Column(db.Numeric(5, 2), default=0)
    sgst_rate = db.Column(db.Numeric(5, 2), default=0)
    igst_rate = db.Column(db.Numeric(5, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_rate = db.Column(db.Numeric(5, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    sort_order = db.Column(db.Integer, default=0)

    def calculate(self, is_igst=False):
        amt = float(self.qty) * float(self.rate)
        disc_amt = amt * float(self.discount_pct) / 100
        taxable = amt - disc_amt
        gst = float(self.gst_rate)
        cess = float(self.cess_rate)

        self.amount = round(amt, 2)
        self.discount_amount = round(disc_amt, 2)
        self.taxable_amount = round(taxable, 2)

        if is_igst:
            self.igst_rate = gst
            self.igst_amount = round(taxable * gst / 100, 2)
            self.cgst_rate = 0
            self.sgst_rate = 0
            self.cgst_amount = 0
            self.sgst_amount = 0
        else:
            self.cgst_rate = gst / 2
            self.sgst_rate = gst / 2
            self.cgst_amount = round(taxable * (gst / 2) / 100, 2)
            self.sgst_amount = round(taxable * (gst / 2) / 100, 2)
            self.igst_rate = 0
            self.igst_amount = 0

        self.cess_amount = round(taxable * cess / 100, 2)

    def __repr__(self):
        return f'<InvoiceItem {self.description}>'
