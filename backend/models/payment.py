from extensions import db
from datetime import datetime

class Payment(db.Model):
    __tablename__ = 'payments'
    __table_args__ = (
        db.Index('idx_pay_org_date', 'org_id', 'payment_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_mode = db.Column(db.String(20), default='cash')  # cash/bank/upi/cheque/neft
    reference_no = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Payment {self.amount} for Invoice {self.invoice_id}>'


class CreditNote(db.Model):
    __tablename__ = 'credit_notes'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    credit_note_no = db.Column(db.String(50), nullable=False)
    credit_note_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))
    amount = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default='open')  # open/applied
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CreditNote {self.credit_note_no}>'
