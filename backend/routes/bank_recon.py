from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.payment import Payment
from models.invoice import Invoice
from models.organization import Organization
from datetime import date, datetime
import io
import csv

bank_recon_bp = Blueprint('bank_recon', __name__)

def org_id():
    return current_user.org_id

@bank_recon_bp.route('/bank-reconciliation', methods=['GET', 'POST'])
@login_required
def index():
    """Bank Reconciliation — Upload CSV bank statement and match payments"""
    bank_transactions = []
    unmatched = []
    matched = []
    summary = {}

    if request.method == 'POST' and 'bank_csv' in request.files:
        file = request.files['bank_csv']
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file.', 'danger')
            return redirect(url_for('bank_recon.index'))

        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        # Try to detect columns (Date, Description/Narration, Credit/Debit/Amount)
        col_date = next((k for k in (rows[0].keys() if rows else [])
                         if any(x in k.lower() for x in ['date', 'dt'])), None)
        col_desc = next((k for k in (rows[0].keys() if rows else [])
                         if any(x in k.lower() for x in ['narrat', 'descrip', 'remark', 'particulars'])), None)
        col_credit = next((k for k in (rows[0].keys() if rows else [])
                           if any(x in k.lower() for x in ['credit', 'deposit', 'cr'])), None)
        col_debit = next((k for k in (rows[0].keys() if rows else [])
                          if any(x in k.lower() for x in ['debit', 'withdrawal', 'dr'])), None)
        col_amount = next((k for k in (rows[0].keys() if rows else [])
                           if 'amount' in k.lower() and 'credit' not in k.lower() and 'debit' not in k.lower()), None)

        # Load our payments from DB
        our_payments = Payment.query.filter_by(org_id=org_id()).order_by(Payment.payment_date.desc()).all()
        payment_map = {}
        for p in our_payments:
            key = round(float(p.amount or 0), 0)
            if key not in payment_map:
                payment_map[key] = []
            payment_map[key].append(p)

        total_credits = 0
        for row in rows:
            try:
                credit_val = 0
                if col_credit:
                    raw = str(row.get(col_credit, '') or '').replace(',', '').strip()
                    credit_val = float(raw) if raw else 0
                elif col_amount:
                    raw = str(row.get(col_amount, '') or '').replace(',', '').strip()
                    credit_val = float(raw) if raw else 0

                if credit_val <= 0:
                    continue

                total_credits += credit_val
                desc = str(row.get(col_desc, '') or '')
                txn_date = str(row.get(col_date, '') or '')

                matched_payment = None
                key = round(credit_val, 0)
                if key in payment_map and payment_map[key]:
                    matched_payment = payment_map[key][0]

                entry = {
                    'date': txn_date,
                    'description': desc,
                    'amount': credit_val,
                    'matched_payment': matched_payment
                }
                if matched_payment:
                    matched.append(entry)
                else:
                    unmatched.append(entry)
            except Exception:
                continue

        summary = {
            'total_transactions': len(matched) + len(unmatched),
            'matched': len(matched),
            'unmatched': len(unmatched),
            'total_credits': total_credits
        }

    # Load recent payments for manual view
    recent_payments = Payment.query.filter_by(org_id=org_id()).order_by(Payment.payment_date.desc()).limit(50).all()
    return render_template('bank_recon/index.html',
                           matched=matched, unmatched=unmatched,
                           summary=summary, recent_payments=recent_payments)
