from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.recurring_invoice import RecurringInvoice, RecurringInvoiceItem
from models.invoice import Invoice, InvoiceItem
from models.customer import Customer
from models.item import Item
from models.organization import Organization
from datetime import date

recurring_bp = Blueprint('recurring', __name__)

def org_id():
    return current_user.org_id

# ─── LIST ─────────────────────────────────────────────────
@recurring_bp.route('/recurring-invoices')
@login_required
def list():
    page = request.args.get('page', 1, type=int)
    from sqlalchemy.orm import joinedload
    query = RecurringInvoice.query.options(joinedload(RecurringInvoice.customer)).filter_by(org_id=org_id(), is_active=True)\
        .order_by(RecurringInvoice.next_date.asc())
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    recurrings = pagination.items
    return render_template('recurring/list.html', recurrings=recurrings, pagination=pagination)

# ─── CREATE ───────────────────────────────────────────────
@recurring_bp.route('/recurring-invoices/create', methods=['GET', 'POST'])
@login_required
def create():
    customers = Customer.query.filter_by(org_id=org_id(), is_active=True).order_by(Customer.name).all()
    items = Item.query.filter_by(org_id=org_id(), is_active=True).order_by(Item.name).all()
    org = Organization.query.get(org_id())
    INDIAN_STATES = [
        ('01','Jammu and Kashmir'),('02','Himachal Pradesh'),('03','Punjab'),
        ('04','Chandigarh'),('05','Uttarakhand'),('06','Haryana'),
        ('07','Delhi'),('08','Rajasthan'),('09','Uttar Pradesh'),
        ('10','Bihar'),('11','Sikkim'),('12','Arunachal Pradesh'),
        ('13','Nagaland'),('14','Manipur'),('15','Mizoram'),
        ('16','Tripura'),('17','Meghalaya'),('18','Assam'),
        ('19','West Bengal'),('20','Jharkhand'),('21','Odisha'),
        ('22','Chhattisgarh'),('23','Madhya Pradesh'),('24','Gujarat'),
        ('25','Daman and Diu'),('26','Dadra and Nagar Haveli'),
        ('27','Maharashtra'),('28','Andhra Pradesh'),('29','Karnataka'),
        ('30','Goa'),('31','Lakshadweep'),('32','Kerala'),
        ('33','Tamil Nadu'),('34','Puducherry'),('35','Andaman and Nicobar'),
        ('36','Telangana'),('37','Andhra Pradesh (New)'),
    ]

    if request.method == 'POST':
        start_date = date.fromisoformat(request.form.get('start_date'))
        r = RecurringInvoice(
            org_id=org_id(),
            customer_id=request.form.get('customer_id'),
            name=request.form.get('name'),
            frequency=request.form.get('frequency', 'monthly'),
            start_date=start_date,
            next_date=start_date,
            end_date=date.fromisoformat(request.form.get('end_date')) if request.form.get('end_date') else None,
            invoice_type=request.form.get('invoice_type', 'tax_invoice'),
            place_of_supply=request.form.get('place_of_supply'),
            is_igst=request.form.get('is_igst') == 'on',
            notes=request.form.get('notes', org.default_notes or ''),
            terms=request.form.get('terms', org.default_terms or ''),
            tds_applicable=request.form.get('tds_applicable') == 'on',
            tds_section=request.form.get('tds_section'),
            tds_rate=request.form.get('tds_rate') or 0,
            auto_send_email=request.form.get('auto_send_email') == 'on',
            created_by=current_user.id
        )
        db.session.add(r)
        db.session.flush()

        descriptions = request.form.getlist('description[]')
        item_ids = request.form.getlist('item_id[]')
        qtys = request.form.getlist('qty[]')
        rates = request.form.getlist('rate[]')
        gst_rates = request.form.getlist('gst_rate[]')
        disc_pcts = request.form.getlist('discount_pct[]')
        hsns = request.form.getlist('hsn_sac[]')
        units = request.form.getlist('unit[]')

        for i, desc in enumerate(descriptions):
            if not desc.strip():
                continue
            ri = RecurringInvoiceItem(
                recurring_id=r.id,
                item_id=item_ids[i] if item_ids[i] else None,
                description=desc,
                hsn_sac=hsns[i] if i < len(hsns) else '',
                qty=float(qtys[i] or 1) if i < len(qtys) else 1,
                unit=units[i] if i < len(units) else 'Nos',
                rate=float(rates[i] or 0) if i < len(rates) else 0,
                discount_pct=float(disc_pcts[i] or 0) if i < len(disc_pcts) else 0,
                gst_rate=float(gst_rates[i] or 18) if i < len(gst_rates) else 18,
                sort_order=i
            )
            db.session.add(ri)

        db.session.commit()
        flash(f'Recurring invoice "{r.name}" created! First invoice on {r.next_date.strftime("%d %b %Y")}.', 'success')
        return redirect(url_for('recurring.list'))

    items_data = [{'id': i.id, 'name': i.name, 'selling_price': float(i.selling_price or 0), 'hsn_sac': i.hsn_sac, 'gst_rate': float(i.gst_rate or 18)} for i in items]
    return render_template('recurring/create.html', customers=customers, items=items_data, org=org, today=date.today(), INDIAN_STATES=INDIAN_STATES)

# ─── GENERATE NOW (manual trigger) ────────────────────────
@recurring_bp.route('/recurring-invoices/<int:id>/generate', methods=['POST'])
@login_required
def generate(id):
    from models.organization import Organization
    r = RecurringInvoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    
    # Get next invoice number
    last = Invoice.query.filter_by(org_id=org_id()).order_by(Invoice.id.desc()).first()
    num = (last.id + 1) if last else org.invoice_start_no
    year = date.today().strftime('%Y')
    inv_no = f"{org.invoice_prefix}-{year}-{num:04d}"

    inv = Invoice(
        org_id=org_id(),
        customer_id=r.customer_id,
        invoice_no=inv_no,
        invoice_type=r.invoice_type,
        invoice_date=date.today(),
        due_date=None,
        place_of_supply=r.place_of_supply,
        is_igst=r.is_igst,
        notes=r.notes,
        terms=r.terms,
        tds_applicable=r.tds_applicable,
        tds_section=r.tds_section,
        tds_rate=r.tds_rate,
        status='draft',
        recurring_id=r.id,
        created_by=current_user.id
    )
    db.session.add(inv)
    db.session.flush()

    for ri in r.items:
        item = InvoiceItem(
            invoice_id=inv.id,
            item_id=ri.item_id,
            description=ri.description,
            hsn_sac=ri.hsn_sac,
            qty=ri.qty,
            unit=ri.unit,
            rate=ri.rate,
            discount_pct=ri.discount_pct,
            gst_rate=ri.gst_rate,
            cess_rate=ri.cess_rate,
            sort_order=ri.sort_order
        )
        item.calculate(is_igst=inv.is_igst)
        db.session.add(item)

    db.session.flush()
    inv.calculate_totals()

    # Update next date
    r.last_generated = date.today()
    r.next_date = r.compute_next_date()
    if r.end_date and r.next_date > r.end_date:
        r.is_active = False

    org.invoice_count_this_month = (org.invoice_count_this_month or 0) + 1
    db.session.commit()

    flash(f'Invoice {inv.invoice_no} generated from recurring template!', 'success')
    return redirect(url_for('invoices.view', id=inv.id))

# ─── TOGGLE ACTIVE ─────────────────────────────────────────
@recurring_bp.route('/recurring-invoices/<int:id>/toggle', methods=['POST'])
@login_required
def toggle(id):
    r = RecurringInvoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    r.is_active = not r.is_active
    db.session.commit()
    flash(f'Recurring invoice {"activated" if r.is_active else "paused"}.', 'success')
    return redirect(url_for('recurring.list'))

# ─── DELETE ─────────────────────────────────────────────────
@recurring_bp.route('/recurring-invoices/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    r = RecurringInvoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    db.session.delete(r)
    db.session.commit()
    flash('Recurring invoice deleted.', 'info')
    return redirect(url_for('recurring.list'))
