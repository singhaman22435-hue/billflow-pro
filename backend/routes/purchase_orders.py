from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.purchase_order import PurchaseOrder, POItem
from models.vendor import Vendor
from models.item import Item
from models.organization import Organization
from datetime import date, datetime

po_bp = Blueprint('purchase_orders', __name__)

def org_id():
    return current_user.org_id

def get_next_po_no(org):
    last = PurchaseOrder.query.filter_by(org_id=org.id).order_by(PurchaseOrder.id.desc()).first()
    num = (last.id + 1) if last else 1
    year = date.today().strftime('%Y')
    return f"{org.po_prefix}-{year}-{num:04d}"

@po_bp.route('/purchase-orders')
@login_required
def list():
    status = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    from sqlalchemy.orm import joinedload
    query = PurchaseOrder.query.options(joinedload(PurchaseOrder.vendor)).filter_by(org_id=org_id())
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(PurchaseOrder.po_date.desc())
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    pos = pagination.items
    return render_template('purchase_orders/list.html', pos=pos, pagination=pagination, status=status)

@po_bp.route('/purchase-orders/create', methods=['GET', 'POST'])
@login_required
def create():
    org = Organization.query.get(org_id())
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('vendor_id'):
            return jsonify({'success': False, 'message': 'Vendor is required.'}), 400

        try:
            p_date = datetime.strptime(data.get('po_date'), '%Y-%m-%d').date() if data.get('po_date') else date.today()
            d_date = datetime.strptime(data.get('delivery_date'), '%Y-%m-%d').date() if data.get('delivery_date') else None

            po = PurchaseOrder(
                org_id=org_id(),
                vendor_id=data.get('vendor_id'),
                po_no=get_next_po_no(org),
                po_date=p_date,
                delivery_date=d_date,
                delivery_address=data.get('delivery_address'),
                is_igst=data.get('is_igst', False),
                notes=data.get('notes'),
                terms=data.get('terms'),
                status='draft',
                created_by=current_user.id
            )
            db.session.add(po)
            db.session.flush()

            subtotal = taxable = cgst = sgst = igst = 0
            for i, row in enumerate(data.get('items', [])):
                desc = row.get('description', '').strip()
                if not desc:
                    continue
                qty = float(row.get('qty') or 1)
                rate = float(row.get('rate') or 0)
                disc = float(row.get('discount_pct') or 0)
                gst = float(row.get('gst_rate') or 0)
                amt = qty * rate
                disc_amt = amt * disc / 100
                tax = amt - disc_amt
                if data.get('is_igst'):
                    ig = round(tax * gst / 100, 2)
                    cg = sg = 0
                else:
                    cg = sg = round(tax * (gst / 2) / 100, 2)
                    ig = 0

                poi = POItem(
                    po_id=po.id,
                    item_id=row.get('item_id'),
                    description=desc,
                    hsn_sac=row.get('hsn_sac'),
                    qty=qty, unit=row.get('unit', 'Nos'), rate=rate,
                    discount_pct=disc, discount_amount=round(disc_amt, 2),
                    amount=round(amt, 2), taxable_amount=round(tax, 2),
                    gst_rate=gst, cgst_amount=cg, sgst_amount=sg, igst_amount=ig,
                    sort_order=i
                )
                db.session.add(poi)
                subtotal += amt; taxable += tax; cgst += cg; sgst += sg; igst += ig

            po.subtotal = round(subtotal, 2)
            po.taxable_amount = round(taxable, 2)
            po.cgst_amount = round(cgst, 2)
            po.sgst_amount = round(sgst, 2)
            po.igst_amount = round(igst, 2)
            po.grand_total = round(taxable + cgst + sgst + igst)
            db.session.commit()
            return jsonify({'success': True, 'po_id': po.id, 'po_no': po.po_no})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error creating PO: {str(e)}'}), 400

    vendors = Vendor.query.filter_by(org_id=org_id(), is_active=True).order_by(Vendor.name).all()
    items = Item.query.filter_by(org_id=org_id(), is_active=True).order_by(Item.name).all()
    return render_template('purchase_orders/create.html', vendors=vendors, items=items,
                           next_no=get_next_po_no(org), org=org, today=date.today())

@po_bp.route('/purchase-orders/<int:id>')
@login_required
def view(id):
    po = PurchaseOrder.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    return render_template('purchase_orders/view.html', po=po, org=org)

@po_bp.route('/purchase-orders/<int:id>/pdf')
@login_required
def download_pdf(id):
    po = PurchaseOrder.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    try:
        from utils.pdf_generator import generate_po_pdf
        pdf_bytes = generate_po_pdf(po, org)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=request.args.get('download') == '1',
            download_name=f'{po.po_no}.pdf'
        )
    except Exception as e:
        flash(f'PO PDF generation error: {str(e)}', 'danger')
        return redirect(url_for('purchase_orders.view', id=id))

@po_bp.route('/purchase-orders/<int:id>/update-status', methods=['POST'])
@login_required
def update_status(id):
    po = PurchaseOrder.query.filter_by(id=id, org_id=org_id()).first_or_404()
    new_status = request.form.get('status')
    if new_status in ['draft', 'sent', 'received', 'cancelled']:
        if po.status != 'received' and new_status == 'received':
            # Add stock
            for item in po.items:
                if item.item_id:
                    prod = Item.query.get(item.item_id)
                    if prod and prod.track_inventory:
                        prod.current_stock = float(prod.current_stock or 0) + float(item.qty or 0)
        elif po.status == 'received' and new_status != 'received':
            # Deduct stock
            for item in po.items:
                if item.item_id:
                    prod = Item.query.get(item.item_id)
                    if prod and prod.track_inventory:
                        prod.current_stock = float(prod.current_stock or 0) - float(item.qty or 0)

        po.status = new_status
        db.session.commit()
        flash(f'PO marked as {new_status}.', 'success')
    return redirect(url_for('purchase_orders.view', id=id))

# ─── PO → EXPENSE CONVERSION ─────────────────────────────
@po_bp.route('/purchase-orders/<int:id>/convert-to-expense', methods=['POST'])
@login_required
def convert_to_expense(id):
    from models.expense import Expense
    po = PurchaseOrder.query.filter_by(id=id, org_id=org_id()).first_or_404()

    exp = Expense(
        org_id=org_id(),
        vendor_id=po.vendor_id,
        expense_date=date.today(),
        category='Purchase',
        description=f'Converted from Purchase Order {po.po_no}',
        amount=float(po.grand_total or 0),
        payment_mode='credit',
        created_by=current_user.id
    )
    db.session.add(exp)
    
    if po.status != 'received':
        # Add stock
        for item in po.items:
            if item.item_id:
                prod = Item.query.get(item.item_id)
                if prod and prod.track_inventory:
                    prod.current_stock = float(prod.current_stock or 0) + float(item.qty or 0)
        po.status = 'received'
        
    db.session.commit()

    flash(f'✅ PO {po.po_no} converted to Expense!', 'success')
    return redirect(url_for('expenses.list'))

