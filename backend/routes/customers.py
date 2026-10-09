from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.customer import Customer

customers_bp = Blueprint('customers', __name__)

def org_id():
    return current_user.org_id

@customers_bp.route('/customers')
@login_required
def list():
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    export = request.args.get('export', '')

    query = Customer.query.filter_by(org_id=org_id(), is_active=True)
    if search:
        query = query.filter(Customer.name.ilike(f'%{search}%'))
    
    query = query.order_by(Customer.name)

    if export == 'csv':
        customers = query.all()
        import io, csv
        from flask import make_response
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Name', 'Email', 'Phone', 'GSTIN', 'Outstanding'])
        for c in customers:
            cw.writerow([c.name, c.email or '', c.phone or '', c.gstin or '', c.get_outstanding()])
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=customers.csv"
        output.headers["Content-type"] = "text/csv"
        return output

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    customers = pagination.items
    return render_template('customers/list.html', customers=customers, pagination=pagination, search=search)

@customers_bp.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        c = Customer(
            org_id=org_id(),
            name=request.form.get('name'),
            display_name=request.form.get('display_name'),
            company_name=request.form.get('company_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            gstin=request.form.get('gstin'),
            pan=request.form.get('pan'),
            state=request.form.get('state'),
            state_code=request.form.get('state_code'),
            billing_address=request.form.get('billing_address'),
            billing_city=request.form.get('billing_city'),
            billing_state=request.form.get('billing_state'),
            billing_pincode=request.form.get('billing_pincode'),
            shipping_address=request.form.get('shipping_address'),
            shipping_city=request.form.get('shipping_city'),
            shipping_state=request.form.get('shipping_state'),
            shipping_pincode=request.form.get('shipping_pincode'),
            credit_limit=request.form.get('credit_limit') or 0,
            opening_balance=request.form.get('opening_balance') or 0,
            payment_terms=request.form.get('payment_terms') or 30,
            notes=request.form.get('notes')
        )
        db.session.add(c)
        db.session.commit()
        flash('Customer added successfully!', 'success')
        return redirect(url_for('customers.list'))
    return render_template('customers/add.html')

@customers_bp.route('/customers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    c = Customer.query.filter_by(id=id, org_id=org_id()).first_or_404()
    if request.method == 'POST':
        c.name = request.form.get('name')
        c.display_name = request.form.get('display_name')
        c.company_name = request.form.get('company_name')
        c.email = request.form.get('email')
        c.phone = request.form.get('phone')
        c.gstin = request.form.get('gstin')
        c.pan = request.form.get('pan')
        c.state = request.form.get('state')
        c.state_code = request.form.get('state_code')
        c.billing_address = request.form.get('billing_address')
        c.billing_city = request.form.get('billing_city')
        c.billing_state = request.form.get('billing_state')
        c.billing_pincode = request.form.get('billing_pincode')
        c.shipping_address = request.form.get('shipping_address')
        c.shipping_city = request.form.get('shipping_city')
        c.shipping_state = request.form.get('shipping_state')
        c.shipping_pincode = request.form.get('shipping_pincode')
        c.credit_limit = request.form.get('credit_limit') or 0
        c.payment_terms = request.form.get('payment_terms') or 30
        c.notes = request.form.get('notes')
        db.session.commit()
        flash('Customer updated!', 'success')
        return redirect(url_for('customers.list'))
    return render_template('customers/add.html', customer=c)

@customers_bp.route('/customers/quick-add', methods=['POST'])
@login_required
def quick_add():
    """API for quick adding a customer from the invoice creation screen"""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'success': False, 'message': 'Name is required'}), 400
        
    c = Customer(
        org_id=org_id(),
        name=data.get('name'),
        phone=data.get('phone', ''),
        state=data.get('state', ''),
        billing_address=data.get('address', ''),
        is_active=True
    )
    
    if data.get('state'):
        c.state_code = data.get('state').split('-')[0]
        
    db.session.add(c)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'customer': {
            'id': c.id,
            'name': c.name,
            'state': c.state,
            'state_code': c.state_code,
            'phone': c.phone,
            'address': c.billing_address
        }
    })

@customers_bp.route('/customers/import', methods=['POST'])
@login_required
def import_csv():
    if 'file' not in request.files:
        flash('No file uploaded.', 'danger')
        return redirect(url_for('customers.list'))
        
    file = request.files['file']
    if file.filename == '':
        flash('No selected file.', 'danger')
        return redirect(url_for('customers.list'))
        
    if file and file.filename.endswith('.csv'):
        import csv
        import io
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        count = 0
        for row in csv_input:
            name = row.get('Name', '').strip()
            if not name:
                continue
                
            customer = Customer(
                org_id=org_id(),
                name=name,
                email=row.get('Email', ''),
                phone=row.get('Phone', ''),
                gstin=row.get('GSTIN', ''),
                state=row.get('State', ''),
                billing_address=row.get('Address', ''),
                is_active=True
            )
            db.session.add(customer)
            count += 1
            
        db.session.commit()
        flash(f'Successfully imported {count} customers.', 'success')
    else:
        flash('Please upload a valid CSV file.', 'danger')
        
    return redirect(url_for('customers.list'))

@customers_bp.route('/customers/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    c = Customer.query.filter_by(id=id, org_id=org_id()).first_or_404()
    c.is_active = False
    db.session.commit()
    flash('Customer deleted.', 'info')
    return redirect(url_for('customers.list'))

@customers_bp.route('/customers/<int:id>')
@login_required
def detail(id):
    c = Customer.query.filter_by(id=id, org_id=org_id()).first_or_404()
    from models.invoice import Invoice
    invoices = Invoice.query.filter_by(customer_id=id, org_id=org_id()).order_by(Invoice.invoice_date.desc()).all()
    return render_template('customers/detail.html', customer=c, invoices=invoices)

# ─── CUSTOMER LEDGER ──────────────────────────────────────
@customers_bp.route('/customers/<int:id>/ledger')
@login_required
def ledger(id):
    from models.invoice import Invoice
    from models.payment import Payment
    c = Customer.query.filter_by(id=id, org_id=org_id()).first_or_404()

    invoices = Invoice.query.filter_by(customer_id=id, org_id=org_id())\
        .order_by(Invoice.invoice_date).all()

    # Get payments via their linked invoices (Payment has no direct customer_id)
    invoice_ids = [inv.id for inv in invoices]
    payments = Payment.query.filter(Payment.invoice_id.in_(invoice_ids))\
        .order_by(Payment.payment_date).all() if invoice_ids else []

    # Build ledger entries (chronological)
    entries = []
    for inv in invoices:
        entries.append({
            'date': inv.invoice_date,
            'type': 'invoice',
            'ref': inv.invoice_no,
            'id': inv.id,
            'debit': float(inv.grand_total),
            'credit': 0,
        })
    for pmt in payments:
        entries.append({
            'date': pmt.payment_date,
            'type': 'payment',
            'ref': pmt.reference_no or f'PMT-{pmt.id}',
            'id': pmt.id,
            'debit': 0,
            'credit': float(pmt.amount),
        })
    entries.sort(key=lambda x: x['date'])

    # Running balance
    balance = float(c.opening_balance or 0)
    for e in entries:
        balance += e['debit'] - e['credit']
        e['balance'] = balance

    total_invoiced = sum(e['debit'] for e in entries)
    total_paid = sum(e['credit'] for e in entries)
    closing_balance = float(c.opening_balance or 0) + total_invoiced - total_paid

    return render_template('customers/ledger.html',
        customer=c, entries=entries,
        total_invoiced=total_invoiced, total_paid=total_paid,
        closing_balance=closing_balance)

# ─── SEND STATEMENT EMAIL ─────────────────────────────────
@customers_bp.route('/customers/<int:id>/send-statement', methods=['POST'])
@login_required
def send_statement(id):
    from models.invoice import Invoice
    from models.organization import Organization
    c = Customer.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())

    if not c.email:
        flash('Customer has no email address.', 'danger')
        return redirect(url_for('customers.ledger', id=id))

    outstanding_invoices = Invoice.query.filter_by(
        customer_id=id, org_id=org_id()
    ).filter(Invoice.status.in_(['sent', 'partial'])).order_by(Invoice.invoice_date).all()

    try:
        from flask_mail import Message
        from extensions import mail
        rows = '\n'.join([
            f"  {inv.invoice_no} | {inv.invoice_date} | ₹{inv.grand_total} | ₹{inv.balance_due} due"
            for inv in outstanding_invoices
        ])
        total_due = sum(float(inv.balance_due) for inv in outstanding_invoices)
        msg = Message(
            subject=f'Account Statement from {org.name}',
            sender=f'{org.name} <{org.email or "noreply@billflowpro.com"}>',
            recipients=[c.email]
        )
        msg.body = f"""Dear {c.name},

Please find your account statement from {org.name}.

Outstanding Invoices:
{rows}

Total Outstanding: ₹{total_due:,.2f}

Please arrange payment at the earliest.

Regards,
{org.name}
{org.phone or ''}
"""
        mail.send(msg)
        flash(f'Statement sent to {c.email}!', 'success')
    except Exception as e:
        flash(f'Email failed: {str(e)}', 'danger')

    return redirect(url_for('customers.ledger', id=id))

# ─── CUSTOMER PORTAL (public link) ───────────────────────
@customers_bp.route('/customers/<int:id>/generate-portal-link', methods=['POST'])
@login_required
def generate_portal_link(id):
    import secrets
    c = Customer.query.filter_by(id=id, org_id=org_id()).first_or_404()
    if not c.portal_token:
        c.portal_token = secrets.token_urlsafe(32)
        db.session.commit()
    flash('Portal link generated!', 'success')
    return redirect(url_for('customers.ledger', id=id))

@customers_bp.route('/api/customers/search')
@login_required
def api_search():
    q = request.args.get('q', '')
    customers = Customer.query.filter_by(org_id=org_id(), is_active=True).filter(
        Customer.name.ilike(f'%{q}%')
    ).limit(10).all()
    return jsonify([{'id': c.id, 'name': c.name, 'gstin': c.gstin or '',
                     'state': c.state or '', 'state_code': c.state_code or ''} for c in customers])

