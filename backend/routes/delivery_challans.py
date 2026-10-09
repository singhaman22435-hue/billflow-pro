from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.expense import DeliveryChallan, DCItem
from models.customer import Customer
from models.item import Item
from models.organization import Organization
from datetime import date, datetime
import io

dc_bp = Blueprint('delivery_challans', __name__)

def org_id():
    return current_user.org_id

def get_next_dc_no(org):
    last = DeliveryChallan.query.filter_by(org_id=org.id).order_by(DeliveryChallan.id.desc()).first()
    num = (last.id + 1) if last else 1
    year = date.today().strftime('%Y')
    return f"DC-{year}-{num:04d}"

@dc_bp.route('/delivery-challans')
@login_required
def list():
    status = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    from sqlalchemy.orm import joinedload
    query = DeliveryChallan.query.options(joinedload(DeliveryChallan.customer)).filter_by(org_id=org_id())
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(DeliveryChallan.dc_date.desc())
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    challans = pagination.items
    return render_template('delivery_challans/list.html', challans=challans, pagination=pagination, status=status)

@dc_bp.route('/delivery-challans/create', methods=['GET', 'POST'])
@login_required
def create():
    org = Organization.query.get(org_id())
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('customer_id'):
            return jsonify({'success': False, 'message': 'Customer is required.'}), 400

        try:
            d_date = datetime.strptime(data.get('dc_date'), '%Y-%m-%d').date() if data.get('dc_date') else date.today()

            dc = DeliveryChallan(
                org_id=org_id(),
                customer_id=data.get('customer_id'),
                dc_no=get_next_dc_no(org),
                dc_date=d_date,
                dc_type=data.get('dc_type', 'delivery'),
                vehicle_no=data.get('vehicle_no'),
                driver_name=data.get('driver_name'),
                delivery_address=data.get('delivery_address'),
                notes=data.get('notes'),
                status='draft',
                created_by=current_user.id
            )
            db.session.add(dc)
            db.session.flush()

            for i, row in enumerate(data.get('items', [])):
                desc = row.get('description', '').strip()
                if not desc:
                    continue
                dci = DCItem(
                    dc_id=dc.id,
                    item_id=row.get('item_id'),
                    description=desc,
                    hsn_sac=row.get('hsn_sac'),
                    qty=float(row.get('qty', 1) or 1),
                    unit=row.get('unit', 'Nos'),
                    remarks=row.get('remarks', ''),
                    sort_order=i
                )
                db.session.add(dci)
            db.session.commit()
            return jsonify({'success': True, 'dc_id': dc.id, 'dc_no': dc.dc_no})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error creating Delivery Challan: {str(e)}'}), 400

    customers = Customer.query.filter_by(org_id=org_id(), is_active=True).order_by(Customer.name).all()
    items = Item.query.filter_by(org_id=org_id(), is_active=True).order_by(Item.name).all()
    return render_template('delivery_challans/create.html', customers=customers, items=items,
                           next_no=get_next_dc_no(org), today=date.today())

@dc_bp.route('/delivery-challans/<int:id>')
@login_required
def view(id):
    dc = DeliveryChallan.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    return render_template('delivery_challans/view.html', dc=dc, org=org)

@dc_bp.route('/delivery-challans/<int:id>/pdf')
@login_required
def download_pdf(id):
    dc = DeliveryChallan.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    try:
        from utils.pdf_generator import generate_dc_pdf
        pdf_bytes = generate_dc_pdf(dc, org)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=request.args.get('download') == '1',
            download_name=f'{dc.dc_no}.pdf'
        )
    except Exception as e:
        flash(f'DC PDF error: {str(e)}', 'danger')
        return redirect(url_for('delivery_challans.view', id=id))

@dc_bp.route('/delivery-challans/<int:id>/update-status', methods=['POST'])
@login_required
def update_status(id):
    dc = DeliveryChallan.query.filter_by(id=id, org_id=org_id()).first_or_404()
    new_status = request.form.get('status')
    if new_status in ['draft', 'dispatched', 'delivered', 'cancelled']:
        dc.status = new_status
        db.session.commit()
        flash(f'Challan marked as {new_status}.', 'success')
    return redirect(url_for('delivery_challans.view', id=id))

@dc_bp.route('/delivery-challans/<int:id>/convert-to-invoice', methods=['POST'])
@login_required
def convert_to_invoice(id):
    from models.invoice import Invoice, InvoiceItem
    from routes.invoices import get_next_invoice_no
    
    dc = DeliveryChallan.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    
    if not org.can_create_invoice():
        flash('Monthly invoice limit reached.', 'warning')
        return redirect(url_for('delivery_challans.view', id=id))
        
    inv = Invoice(
        org_id=org_id(),
        customer_id=dc.customer_id,
        invoice_no=get_next_invoice_no(org),
        invoice_type='tax_invoice',
        invoice_date=date.today(),
        place_of_supply=dc.customer.state or '',
        is_igst=False,  # Can be adjusted by user
        notes=f"Generated from Delivery Challan {dc.dc_no}",
        status='draft',
        created_by=current_user.id
    )
    db.session.add(inv)
    db.session.flush()
    
    for i, dc_item in enumerate(dc.items):
        rate = 0
        gst_rate = 18
        if dc_item.item_id:
            item_db = Item.query.get(dc_item.item_id)
            if item_db:
                rate = float(item_db.selling_price or 0)
                gst_rate = float(item_db.gst_rate or 18)
                
        inv_item = InvoiceItem(
            invoice_id=inv.id,
            item_id=dc_item.item_id,
            description=dc_item.description,
            hsn_sac=dc_item.hsn_sac,
            qty=dc_item.qty,
            unit=dc_item.unit,
            rate=rate,
            gst_rate=gst_rate,
            sort_order=i
        )
        inv_item.calculate(is_igst=False)
        db.session.add(inv_item)
        
    db.session.flush()
    inv.calculate_totals()
    org.invoice_count_this_month += 1
    dc.invoice_id = inv.id
    db.session.commit()
    
    flash(f'Draft Invoice created from DC {dc.dc_no}. Please review rates and taxes.', 'success')
    return redirect(url_for('invoices.edit', id=inv.id))
