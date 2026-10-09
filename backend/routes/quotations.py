from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from extensions import db
from models.quotation import Quotation, QuotationItem
from models.customer import Customer
from models.item import Item
from models.organization import Organization
from models.invoice import Invoice, InvoiceItem
from datetime import date, datetime
import io

quotations_bp = Blueprint('quotations', __name__)

def org_id():
    return current_user.org_id

def get_next_quotation_no(org):
    last = Quotation.query.filter_by(org_id=org.id).order_by(Quotation.id.desc()).first()
    num = (last.id + 1) if last else 1
    year = date.today().strftime('%Y')
    return f"{org.quotation_prefix}-{year}-{num:04d}"

@quotations_bp.route('/quotations')
@login_required
def list():
    page = request.args.get('page', 1, type=int)
    from sqlalchemy.orm import joinedload
    query = Quotation.query.options(joinedload(Quotation.customer)).filter_by(org_id=org_id()).order_by(Quotation.quotation_date.desc())
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    quotations = pagination.items
    return render_template('quotations/list.html', quotations=quotations, pagination=pagination)

@quotations_bp.route('/quotations/create', methods=['GET', 'POST'])
@login_required
def create():
    org = Organization.query.get(org_id())
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('customer_id'):
            return jsonify({'success': False, 'message': 'Customer is required.'}), 400
        
        try:
            q_date = datetime.strptime(data.get('quotation_date'), '%Y-%m-%d').date() if data.get('quotation_date') else date.today()
            v_till = datetime.strptime(data.get('valid_till'), '%Y-%m-%d').date() if data.get('valid_till') else None
            
            qt = Quotation(
                org_id=org_id(),
                customer_id=data.get('customer_id'),
                quotation_no=get_next_quotation_no(org),
                quotation_date=q_date,
                valid_till=v_till,
                is_igst=data.get('is_igst', False),
                notes=data.get('notes'),
                terms=data.get('terms'),
                status='draft',
                created_by=current_user.id
            )
            db.session.add(qt)
            db.session.flush()

            for i, row in enumerate(data.get('items', [])):
                desc = row.get('description', '').strip()
                if not desc:
                    continue
                qi = QuotationItem(
                    quotation_id=qt.id,
                    item_id=row.get('item_id'),
                    description=desc,
                    hsn_sac=row.get('hsn_sac'),
                    qty=float(row.get('qty', 1) or 1),
                    unit=row.get('unit', 'Nos'),
                    rate=float(row.get('rate', 0) or 0),
                    discount_pct=float(row.get('discount_pct', 0) or 0),
                    gst_rate=float(row.get('gst_rate', 0) or 0),
                    sort_order=i
                )
                db.session.add(qi)

            db.session.commit()
            return jsonify({'success': True, 'quotation_id': qt.id})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error creating quotation: {str(e)}'}), 400

    customers = Customer.query.filter_by(org_id=org_id(), is_active=True).all()
    items = Item.query.filter_by(org_id=org_id(), is_active=True).all()
    return render_template('quotations/create.html', customers=customers, items=items,
                           next_no=get_next_quotation_no(org), org=org, today=date.today())

@quotations_bp.route('/quotations/<int:id>')
@login_required
def view(id):
    qt = Quotation.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    return render_template('quotations/view.html', qt=qt, org=org)

@quotations_bp.route('/quotations/<int:id>/pdf')
@login_required
def download_pdf(id):
    qt = Quotation.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    try:
        from utils.pdf_generator import generate_quotation_pdf
        pdf_bytes = generate_quotation_pdf(qt, org)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=request.args.get('download') == '1',
            download_name=f'{qt.quotation_no}.pdf'
        )
    except Exception as e:
        flash(f'Quotation PDF error: {str(e)}', 'danger')
        return redirect(url_for('quotations.view', id=id))

@quotations_bp.route('/quotations/<int:id>/update-status', methods=['POST'])
@login_required
def update_status(id):
    qt = Quotation.query.filter_by(id=id, org_id=org_id()).first_or_404()
    new_status = request.form.get('status')
    if new_status in ['draft', 'sent', 'accepted', 'rejected']:
        qt.status = new_status
        db.session.commit()
        flash(f'Quotation marked as {new_status}.', 'success')
    return redirect(url_for('quotations.view', id=id))

@quotations_bp.route('/quotations/<int:id>/convert', methods=['POST'])
@login_required
def convert_to_invoice(id):
    qt = Quotation.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())

    from routes.invoices import get_next_invoice_no
    invoice = Invoice(
        org_id=org_id(),
        customer_id=qt.customer_id,
        invoice_no=get_next_invoice_no(org),
        invoice_date=date.today(),
        is_igst=qt.is_igst,
        notes=qt.notes,
        terms=qt.terms,
        status='draft',
        created_by=current_user.id
    )
    db.session.add(invoice)
    db.session.flush()

    for qi in qt.items:
        inv_item = InvoiceItem(
            invoice_id=invoice.id,
            item_id=qi.item_id,
            description=qi.description,
            hsn_sac=qi.hsn_sac,
            qty=qi.qty,
            unit=qi.unit,
            rate=qi.rate,
            discount_pct=qi.discount_pct,
            gst_rate=qi.gst_rate,
            cess_rate=0
        )
        inv_item.calculate(is_igst=qt.is_igst)
        db.session.add(inv_item)

    db.session.flush()
    invoice.calculate_totals()
    qt.status = 'converted'
    qt.converted_invoice_id = invoice.id
    org.invoice_count_this_month += 1
    db.session.commit()

    flash(f'Quotation converted to {invoice.invoice_no}!', 'success')
    return redirect(url_for('invoices.view', id=invoice.id))
