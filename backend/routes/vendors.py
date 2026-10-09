from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.vendor import Vendor

vendors_bp = Blueprint('vendors', __name__)

def org_id():
    return current_user.org_id

@vendors_bp.route('/vendors')
@login_required
def list():
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    export = request.args.get('export', '')

    query = Vendor.query.filter_by(org_id=org_id(), is_active=True)
    if search:
        query = query.filter(Vendor.name.ilike(f'%{search}%'))
    
    query = query.order_by(Vendor.name)

    if export == 'csv':
        vendors = query.all()
        import io, csv
        from flask import make_response
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Name', 'Email', 'Phone', 'GSTIN', 'State'])
        for v in vendors:
            cw.writerow([v.name, v.email or '', v.phone or '', v.gstin or '', v.state or ''])
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=vendors.csv"
        output.headers["Content-type"] = "text/csv"
        return output

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    vendors = pagination.items
    return render_template('vendors/list.html', vendors=vendors, pagination=pagination, search=search)

@vendors_bp.route('/vendors/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        v = Vendor(
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
            address=request.form.get('address'),
            city=request.form.get('city'),
            pincode=request.form.get('pincode'),
            opening_balance=request.form.get('opening_balance') or 0,
            payment_terms=request.form.get('payment_terms') or 30,
            notes=request.form.get('notes')
        )
        db.session.add(v)
        db.session.commit()
        flash('Vendor added successfully!', 'success')
        return redirect(url_for('vendors.list'))
    return render_template('vendors/add.html')

@vendors_bp.route('/vendors/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    v = Vendor.query.filter_by(id=id, org_id=org_id()).first_or_404()
    if request.method == 'POST':
        v.name = request.form.get('name')
        v.display_name = request.form.get('display_name')
        v.company_name = request.form.get('company_name')
        v.email = request.form.get('email')
        v.phone = request.form.get('phone')
        v.gstin = request.form.get('gstin')
        v.pan = request.form.get('pan')
        v.state = request.form.get('state')
        v.state_code = request.form.get('state_code')
        v.address = request.form.get('address')
        v.city = request.form.get('city')
        v.pincode = request.form.get('pincode')
        v.payment_terms = request.form.get('payment_terms') or 30
        v.notes = request.form.get('notes')
        db.session.commit()
        flash('Vendor updated!', 'success')
        return redirect(url_for('vendors.list'))
    return render_template('vendors/add.html', vendor=v)

@vendors_bp.route('/vendors/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    v = Vendor.query.filter_by(id=id, org_id=org_id()).first_or_404()
    v.is_active = False
    db.session.commit()
    flash('Vendor deleted.', 'info')
    return redirect(url_for('vendors.list'))

@vendors_bp.route('/api/vendors/search')
@login_required
def api_search():
    q = request.args.get('q', '')
    vendors = Vendor.query.filter_by(org_id=org_id(), is_active=True).filter(
        Vendor.name.ilike(f'%{q}%')
    ).limit(10).all()
    return jsonify([{'id': v.id, 'name': v.name, 'gstin': v.gstin or '',
                     'state': v.state or '', 'state_code': v.state_code or ''} for v in vendors])

# ─── VENDOR LEDGER ────────────────────────────────────────
@vendors_bp.route('/vendors/<int:id>/ledger')
@login_required
def ledger(id):
    from models.expense import Expense
    from models.purchase_order import PurchaseOrder
    v = Vendor.query.filter_by(id=id, org_id=org_id()).first_or_404()

    expenses = Expense.query.filter_by(vendor_id=id, org_id=org_id())\
        .order_by(Expense.expense_date).all()
    pos = PurchaseOrder.query.filter_by(vendor_id=id, org_id=org_id())\
        .order_by(PurchaseOrder.po_date).all()

    entries = []
    for po in pos:
        entries.append({
            'date': po.po_date,
            'type': 'purchase_order',
            'ref': po.po_no,
            'id': po.id,
            'debit': float(po.grand_total or 0),
            'credit': 0
        })
    for exp in expenses:
        entries.append({
            'date': exp.expense_date,
            'type': 'expense',
            'ref': exp.reference_no or f'EXP-{exp.id}',
            'id': exp.id,
            'debit': 0,
            'credit': float(exp.amount or 0)
        })
    entries.sort(key=lambda x: x['date'])

    balance = 0
    for e in entries:
        balance += e['debit'] - e['credit']
        e['balance'] = balance

    total_purchases = sum(e['debit'] for e in entries)
    total_paid = sum(e['credit'] for e in entries)

    return render_template('vendors/ledger.html',
        vendor=v, entries=entries,
        total_purchases=total_purchases, total_paid=total_paid,
        closing_balance=total_purchases - total_paid)

