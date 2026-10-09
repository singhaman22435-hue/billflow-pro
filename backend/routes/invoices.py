from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from extensions import db
from models.invoice import Invoice, InvoiceItem
from models.customer import Customer
from models.item import Item
from models.payment import Payment
from models.organization import Organization
from datetime import date, datetime
import io

invoices_bp = Blueprint('invoices', __name__)

def org_id():
    return current_user.org_id

def get_next_invoice_no(org):
    last = Invoice.query.filter_by(org_id=org.id).order_by(Invoice.id.desc()).first()
    num = (last.id + 1) if last else org.invoice_start_no
    year = date.today().strftime('%Y')
    return f"{org.invoice_prefix}-{year}-{num:04d}"

@invoices_bp.route('/invoices')
@login_required
def list():
    status = request.args.get('status', '')
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    export = request.args.get('export', '')
    
    from sqlalchemy.orm import joinedload
    query = Invoice.query.options(joinedload(Invoice.customer)).filter_by(org_id=org_id())
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.join(Customer).filter(Customer.name.ilike(f'%{search}%'))
    
    query = query.order_by(Invoice.invoice_date.desc())
    
    if export == 'csv':
        invoices = query.all()
        import io, csv
        from flask import make_response
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Invoice No', 'Customer', 'Date', 'Due Date', 'Grand Total', 'Balance Due', 'Status'])
        for inv in invoices:
            cw.writerow([
                inv.invoice_no,
                inv.customer.name,
                inv.invoice_date.strftime('%Y-%m-%d'),
                inv.due_date.strftime('%Y-%m-%d') if inv.due_date else '',
                inv.grand_total,
                inv.balance_due,
                inv.status
            ])
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=invoices.csv"
        output.headers["Content-type"] = "text/csv"
        return output
        
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    invoices = pagination.items
    return render_template('invoices/list.html', invoices=invoices, pagination=pagination, status=status, search=search, today=date.today())

@invoices_bp.route('/invoices/create', methods=['GET', 'POST'])
@login_required
def create():
    org = Organization.query.get(org_id())
    if not org.can_create_invoice():
        flash('Monthly invoice limit reached for your current plan. Upgrade your subscription to continue.', 'warning')
        return redirect(url_for('subscription.pricing'))

    if request.method == 'POST':
        data = request.get_json()
        if not data:
            flash('Invalid data.', 'danger')
            return redirect(url_for('invoices.create'))

        customer_id = data.get('customer_id')
        invoice_date_str = data.get('invoice_date')
        due_date_str = data.get('due_date')
        is_igst = data.get('is_igst', False)

        invoice = Invoice(
            org_id=org_id(),
            customer_id=customer_id,
            invoice_no=get_next_invoice_no(org),
            invoice_type=data.get('invoice_type', 'tax_invoice'),
            invoice_date=datetime.strptime(invoice_date_str, '%Y-%m-%d').date(),
            due_date=datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None,
            place_of_supply=data.get('place_of_supply'),
            is_igst=is_igst,
            notes=data.get('notes'),
            terms=data.get('terms'),
            status='draft',
            created_by=current_user.id
        )
        db.session.add(invoice)
        db.session.flush()

        for i, row in enumerate(data.get('items', [])):
            inv_item = InvoiceItem(
                invoice_id=invoice.id,
                item_id=row.get('item_id'),
                description=row.get('description'),
                hsn_sac=row.get('hsn_sac'),
                qty=row.get('qty', 1),
                unit=row.get('unit', 'Nos'),
                rate=row.get('rate', 0),
                discount_pct=row.get('discount_pct', 0),
                gst_rate=row.get('gst_rate', 0),
                cess_rate=row.get('cess_rate', 0),
                sort_order=i
            )
            inv_item.calculate(is_igst=is_igst)
            db.session.add(inv_item)

            # Deduct inventory
            if inv_item.item_id:
                item = Item.query.get(inv_item.item_id)
                if item and item.track_inventory:
                    item.current_stock = float(item.current_stock or 0) - float(inv_item.qty or 0)

        db.session.flush()
        invoice.calculate_totals()
        org.invoice_count_this_month += 1
        db.session.commit()
        
        # Invalidate dashboard cache
        from extensions import cache
        cache.delete(f"dashboard_{org_id()}")

        return jsonify({'success': True, 'invoice_id': invoice.id, 'invoice_no': invoice.invoice_no})

    customers = Customer.query.filter_by(org_id=org_id(), is_active=True).order_by(Customer.name).all()
    items = Item.query.filter_by(org_id=org_id(), is_active=True).order_by(Item.name).all()
    
    items_data = [{
        'id': i.id,
        'name': i.name,
        'hsn_sac': i.hsn_sac or '',
        'unit': i.unit or 'Nos',
        'selling_price': float(i.selling_price) if i.selling_price else 0.0,
        'tax_rate': float(i.gst_rate) if i.gst_rate else 0.0,
        'cess_rate': float(i.cess_rate) if i.cess_rate else 0.0,
        'description': i.description or ''
    } for i in items]
    
    next_no = get_next_invoice_no(org)
    INDIAN_STATES = [
        ('01', 'Jammu and Kashmir'), ('02', 'Himachal Pradesh'), ('03', 'Punjab'),
        ('04', 'Chandigarh'), ('05', 'Uttarakhand'), ('06', 'Haryana'),
        ('07', 'Delhi'), ('08', 'Rajasthan'), ('09', 'Uttar Pradesh'),
        ('10', 'Bihar'), ('11', 'Sikkim'), ('12', 'Arunachal Pradesh'),
        ('13', 'Nagaland'), ('14', 'Manipur'), ('15', 'Mizoram'),
        ('16', 'Tripura'), ('17', 'Meghalaya'), ('18', 'Assam'),
        ('19', 'West Bengal'), ('20', 'Jharkhand'), ('21', 'Odisha'),
        ('22', 'Chhattisgarh'), ('23', 'Madhya Pradesh'), ('24', 'Gujarat'),
        ('27', 'Maharashtra'), ('29', 'Karnataka'), ('30', 'Goa'),
        ('32', 'Kerala'), ('33', 'Tamil Nadu'), ('34', 'Puducherry'),
        ('36', 'Telangana'), ('37', 'Andhra Pradesh')
    ]
    return render_template('invoices/create.html', customers=customers, items=items_data,
                           next_no=next_no, org=org, today=date.today(),
                           INDIAN_STATES=INDIAN_STATES)

@invoices_bp.route('/invoices/<int:id>')
@login_required
def view(id):
    invoice = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    return render_template('invoices/view.html', invoice=invoice, org=org, today=date.today())

@invoices_bp.route('/invoices/<int:id>/update-status', methods=['POST'])
@login_required
def update_status(id):
    invoice = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    new_status = request.form.get('status')
    if new_status in ['draft', 'sent', 'cancelled']:
        if invoice.status != 'cancelled' and new_status == 'cancelled':
            # Restore stock
            for item in invoice.items:
                if item.item_id:
                    prod = Item.query.get(item.item_id)
                    if prod and prod.track_inventory:
                        prod.current_stock = float(prod.current_stock or 0) + float(item.qty or 0)
        elif invoice.status == 'cancelled' and new_status != 'cancelled':
            # Deduct stock
            for item in invoice.items:
                if item.item_id:
                    prod = Item.query.get(item.item_id)
                    if prod and prod.track_inventory:
                        prod.current_stock = float(prod.current_stock or 0) - float(item.qty or 0)
        
        invoice.status = new_status
        db.session.commit()
        flash(f'Invoice marked as {new_status}.', 'success')
    return redirect(url_for('invoices.view', id=id))

@invoices_bp.route('/invoices/<int:id>/payment', methods=['POST'])
@login_required
def record_payment(id):
    invoice = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    amount = float(request.form.get('amount', 0))
    payment_date_str = request.form.get('payment_date')
    mode = request.form.get('payment_mode', 'cash')
    ref = request.form.get('reference_no', '')

    if amount <= 0:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('invoices.view', id=id))

    payment = Payment(
        org_id=org_id(),
        invoice_id=invoice.id,
        amount=amount,
        payment_date=datetime.strptime(payment_date_str, '%Y-%m-%d').date(),
        payment_mode=mode,
        reference_no=ref,
        created_by=current_user.id
    )
    db.session.add(payment)

    invoice.amount_paid = float(invoice.amount_paid) + amount
    invoice.balance_due = float(invoice.grand_total) - float(invoice.amount_paid)
    if invoice.balance_due <= 0:
        invoice.status = 'paid'
        invoice.balance_due = 0
    else:
        invoice.status = 'partial'

    db.session.commit()
    
    # Invalidate dashboard cache
    from extensions import cache
    cache.delete(f"dashboard_{org_id()}")
    
    flash(f'Payment of ₹{amount:,.2f} recorded!', 'success')
    return redirect(url_for('invoices.view', id=id))

@invoices_bp.route('/invoices/<int:id>/pdf')
@login_required
def download_pdf(id):
    invoice = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    try:
        from utils.pdf_generator import generate_invoice_pdf
        pdf_bytes = generate_invoice_pdf(invoice, org)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=request.args.get('download') == '1',
            download_name=f'{invoice.invoice_no}.pdf'
        )
    except Exception as e:
        flash(f'PDF generation error: {str(e)}', 'danger')
        return redirect(url_for('invoices.view', id=id))

@invoices_bp.route('/invoices/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    try:
        invoice = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
        if invoice.status in ['paid', 'cancelled']:
            flash('Cannot edit a paid or cancelled invoice.', 'warning')
            return redirect(url_for('invoices.view', id=id))

        org = Organization.query.get(org_id())

        if request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Invalid data'}), 400

            invoice.customer_id = data.get('customer_id', invoice.customer_id)
            invoice.invoice_type = data.get('invoice_type', invoice.invoice_type)
            invoice.invoice_date = datetime.strptime(data.get('invoice_date'), '%Y-%m-%d').date()
            due_date_str = data.get('due_date')
            invoice.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
            invoice.place_of_supply = data.get('place_of_supply')
            invoice.is_igst = data.get('is_igst', False)
            invoice.notes = data.get('notes')
            invoice.terms = data.get('terms')

            # Restore stock from old items
            old_items = InvoiceItem.query.filter_by(invoice_id=invoice.id).all()
            for old_it in old_items:
                if old_it.item_id:
                    prod = Item.query.get(old_it.item_id)
                    if prod and prod.track_inventory:
                        prod.current_stock = float(prod.current_stock or 0) + float(old_it.qty or 0)
            
            # Delete old items and re-create
            InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
            db.session.flush()

            for i, row in enumerate(data.get('items', [])):
                inv_item = InvoiceItem(
                    invoice_id=invoice.id,
                    item_id=row.get('item_id'),
                    description=row.get('description'),
                    hsn_sac=row.get('hsn_sac'),
                    qty=row.get('qty', 1),
                    unit=row.get('unit', 'Nos'),
                    rate=row.get('rate', 0),
                    discount_pct=row.get('discount_pct', 0),
                    gst_rate=row.get('gst_rate', 0),
                    cess_rate=row.get('cess_rate', 0),
                    sort_order=i
                )
                inv_item.calculate(is_igst=invoice.is_igst)
                db.session.add(inv_item)

                # Deduct inventory for new item
                if inv_item.item_id:
                    prod = Item.query.get(inv_item.item_id)
                    if prod and prod.track_inventory:
                        prod.current_stock = float(prod.current_stock or 0) - float(inv_item.qty or 0)

            db.session.flush()
            # Recalculate totals keeping existing payments
            invoice.calculate_totals()
            invoice.balance_due = float(invoice.grand_total) - float(invoice.amount_paid)
            db.session.commit()
            return jsonify({'success': True, 'invoice_id': invoice.id, 'invoice_no': invoice.invoice_no})

        customers = Customer.query.filter_by(org_id=org_id(), is_active=True).order_by(Customer.name).all()
        items = Item.query.filter_by(org_id=org_id(), is_active=True).order_by(Item.name).all()
        items_data = [{
            'id': i.id,
            'name': i.name,
            'hsn_sac': i.hsn_sac or '',
            'unit': i.unit or 'Nos',
            'selling_price': float(i.selling_price) if i.selling_price else 0.0,
            'tax_rate': float(i.gst_rate) if i.gst_rate else 0.0,
            'cess_rate': float(i.cess_rate) if i.cess_rate else 0.0,
            'description': i.description or ''
        } for i in items]

        # Prepare existing items for pre-filling
        existing_items = [{
            'item_id': it.item_id,
            'description': it.description or '',
            'hsn_sac': it.hsn_sac or '',
            'qty': float(it.qty or 0),
            'unit': it.unit or 'Nos',
            'rate': float(it.rate or 0),
            'discount_pct': float(it.discount_pct or 0),
            'gst_rate': float(it.gst_rate or 0),
            'cess_rate': float(it.cess_rate or 0),
        } for it in invoice.items.order_by(InvoiceItem.sort_order)]

        return render_template('invoices/edit.html', invoice=invoice, customers=customers,
                               items=items_data, org=org, today=date.today(),
                               existing_items=existing_items, INDIAN_STATES=INDIAN_STATES)
    except Exception as e:
        import traceback
        flash(f'System Error loading edit page: {traceback.format_exc()}', 'danger')
        return redirect(url_for('invoices.view', id=id))

@invoices_bp.route('/invoices/<int:id>/send-email', methods=['POST'])
@login_required
def send_email(id):
    invoice = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())

    try:
        from utils.pdf_generator import generate_invoice_pdf
        from flask_mail import Message
        from extensions import mail
        import io

        pdf_bytes = generate_invoice_pdf(invoice, org)
        customer_email = invoice.customer.email
        if not customer_email:
            flash('Customer has no email address on file.', 'warning')
            return redirect(url_for('invoices.view', id=id))

        msg = Message(
            subject=f"Invoice {invoice.invoice_no} from {org.name}",
            sender=('BillFlow Pro', 'noreply@billflowpro.com'),
            recipients=[customer_email]
        )
        msg.html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#0f172a;color:#f1f5f9;padding:32px;border-radius:16px;">
            <h2 style="color:#6366f1;margin-bottom:4px;">Invoice from {org.name}</h2>
            <p style="color:#94a3b8;margin-top:0;">Invoice No: <strong style="color:#f1f5f9;">{invoice.invoice_no}</strong></p>
            <hr style="border-color:#1e293b;margin:24px 0;">
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="color:#94a3b8;padding:8px 0;">Invoice Date</td><td style="text-align:right;color:#f1f5f9;">{invoice.invoice_date.strftime('%d %b %Y')}</td></tr>
                <tr><td style="color:#94a3b8;padding:8px 0;">Due Date</td><td style="text-align:right;color:{'#ef4444' if invoice.due_date else '#f1f5f9'};">{invoice.due_date.strftime('%d %b %Y') if invoice.due_date else 'N/A'}</td></tr>
                <tr><td style="color:#94a3b8;padding:8px 0;">Amount Due</td><td style="text-align:right;font-size:1.4rem;font-weight:bold;color:#6366f1;">₹{float(invoice.balance_due):,.2f}</td></tr>
            </table>
            <hr style="border-color:#1e293b;margin:24px 0;">
            <p style="color:#94a3b8;font-size:0.9rem;">Please find the invoice attached to this email. Contact us if you have any questions.</p>
            <p style="margin-top:24px;color:#64748b;font-size:0.8rem;">This is an automated email from BillFlow Pro.</p>
        </div>
        """
        msg.attach(
            f"{invoice.invoice_no}.pdf",
            "application/pdf",
            pdf_bytes
        )
        mail.send(msg)

        # Mark as sent if draft
        if invoice.status == 'draft':
            invoice.status = 'sent'
            db.session.commit()

        flash(f'Invoice emailed to {customer_email} successfully! ✅', 'success')
    except Exception as e:
        flash(f'Failed to send email: {str(e)}', 'danger')

    return redirect(url_for('invoices.view', id=id))

@invoices_bp.route('/invoices/send-reminders', methods=['POST'])
@login_required
def send_reminders():
    from datetime import date
    from flask_mail import Message
    from extensions import mail
    today = date.today()
    org = Organization.query.get(org_id())

    overdue = Invoice.query.filter(
        Invoice.org_id == org_id(),
        Invoice.status.in_(['sent', 'partial']),
        Invoice.due_date < today,
        Invoice.customer_id != None
    ).all()

    sent_count = 0
    for inv in overdue:
        if not inv.customer or not inv.customer.email:
            continue
        try:
            days_overdue = (today - inv.due_date).days
            msg = Message(
                subject=f"Payment Reminder: Invoice {inv.invoice_no} Overdue by {days_overdue} days",
                sender=('BillFlow Pro', 'noreply@billflowpro.com'),
                recipients=[inv.customer.email]
            )
            msg.html = f"""
            <div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#0f172a;color:#f1f5f9;padding:32px;border-radius:16px;">
                <div style="background:#ef444422;border:1px solid #ef4444;border-radius:8px;padding:12px 16px;margin-bottom:24px;">
                    ⚠️ <strong style="color:#ef4444;">Payment Overdue</strong>
                </div>
                <h2 style="color:#f1f5f9;">Dear {inv.customer.name},</h2>
                <p style="color:#94a3b8;">This is a reminder that the following invoice from <strong style="color:#6366f1;">{org.name}</strong> is now overdue.</p>
                <hr style="border-color:#1e293b;margin:24px 0;">
                <table style="width:100%;border-collapse:collapse;">
                    <tr><td style="color:#94a3b8;padding:8px 0;">Invoice No</td><td style="text-align:right;color:#f1f5f9;">{inv.invoice_no}</td></tr>
                    <tr><td style="color:#94a3b8;padding:8px 0;">Due Date</td><td style="text-align:right;color:#ef4444;">{inv.due_date.strftime('%d %b %Y')}</td></tr>
                    <tr><td style="color:#94a3b8;padding:8px 0;">Days Overdue</td><td style="text-align:right;color:#ef4444;font-weight:bold;">{days_overdue} days</td></tr>
                    <tr><td style="color:#94a3b8;padding:8px 0;">Amount Due</td><td style="text-align:right;font-size:1.4rem;font-weight:bold;color:#ef4444;">₹{float(inv.balance_due):,.2f}</td></tr>
                </table>
                <hr style="border-color:#1e293b;margin:24px 0;">
                <p style="color:#94a3b8;font-size:0.9rem;">Please arrange payment at your earliest convenience. Contact us if you have any questions.</p>
            </div>
            """
            mail.send(msg)
            sent_count += 1
        except:
            pass

    if sent_count > 0:
        flash(f'Reminders sent to {sent_count} customer(s) with overdue invoices! ✅', 'success')
    else:
        flash('No overdue invoices with customer emails found.', 'info')

    return redirect(url_for('invoices.list'))
@invoices_bp.route('/invoices/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    invoice = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    
    # Optional: Delete associated payments first if needed (usually cascade deletes handle this)
    Payment.query.filter_by(invoice_id=id).delete()
    InvoiceItem.query.filter_by(invoice_id=id).delete()
    
    db.session.delete(invoice)
    db.session.commit()
    flash(f'Invoice {invoice.invoice_no} deleted successfully.', 'success')
    return redirect(url_for('invoices.list'))

# ─── EXPORT TO CSV ────────────────────────────────────────
@invoices_bp.route('/invoices/export-csv')
@login_required
def export_csv():
    import csv
    invoices = Invoice.query.filter_by(org_id=org_id()).order_by(Invoice.invoice_date.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Invoice No', 'Date', 'Due Date', 'Customer', 'Customer GSTIN',
                     'Status', 'Subtotal', 'Discount', 'Taxable', 'CGST', 'SGST', 'IGST',
                     'Grand Total', 'Amount Paid', 'Balance Due'])
    for inv in invoices:
        writer.writerow([
            inv.invoice_no,
            inv.invoice_date.strftime('%d-%m-%Y'),
            inv.due_date.strftime('%d-%m-%Y') if inv.due_date else '',
            inv.customer.name,
            inv.customer.gstin or '',
            inv.status,
            float(inv.subtotal or 0),
            float(inv.total_discount or 0),
            float(inv.taxable_amount or 0),
            float(inv.cgst_amount or 0),
            float(inv.sgst_amount or 0),
            float(inv.igst_amount or 0),
            float(inv.grand_total or 0),
            float(inv.amount_paid or 0),
            float(inv.balance_due or 0),
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'invoices_{date.today().strftime("%Y%m%d")}.csv'
    )

# ─── DUPLICATE INVOICE ────────────────────────────────────
@invoices_bp.route('/invoices/<int:id>/duplicate', methods=['POST'])
@login_required
def duplicate(id):
    try:
        original = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
        org = Organization.query.get(org_id())
        
        new_inv = Invoice(
            org_id=org_id(),
            customer_id=original.customer_id,
            invoice_no=get_next_invoice_no(org),
            invoice_type=original.invoice_type,
            invoice_date=date.today(),
            due_date=None,
            place_of_supply=original.place_of_supply,
            is_igst=original.is_igst,
            notes=original.notes,
            terms=original.terms,
            status='draft',
            created_by=current_user.id
        )
        db.session.add(new_inv)
        db.session.flush()
        
        for item in original.items:
            new_item = InvoiceItem(
                invoice_id=new_inv.id,
                item_id=item.item_id,
                description=item.description,
                hsn_sac=item.hsn_sac,
                qty=item.qty,
                unit=item.unit,
                rate=item.rate,
                discount_pct=item.discount_pct,
                gst_rate=item.gst_rate,
                cess_rate=item.cess_rate,
                sort_order=item.sort_order
            )
            new_item.calculate(is_igst=new_inv.is_igst)
            db.session.add(new_item)
        
        db.session.flush()
        new_inv.calculate_totals()
        org.invoice_count_this_month = (org.invoice_count_this_month or 0) + 1
        db.session.commit()
        flash(f'Invoice duplicated as {new_inv.invoice_no}!', 'success')
        return redirect(url_for('invoices.edit', id=new_inv.id))
    except Exception as e:
        import traceback
        db.session.rollback()
        flash(f'System Error duplicating invoice: {traceback.format_exc()}', 'danger')
        return redirect(url_for('invoices.list'))

# ─── CREDIT NOTE ──────────────────────────────────────────
@invoices_bp.route('/invoices/<int:id>/credit-note', methods=['POST'])
@login_required
def credit_note(id):
    original = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    
    reason = request.form.get('reason', 'Credit Note')
    
    cn = Invoice(
        org_id=org_id(),
        customer_id=original.customer_id,
        invoice_no='CN-' + original.invoice_no,
        invoice_type='credit_note',
        invoice_date=date.today(),
        place_of_supply=original.place_of_supply,
        is_igst=original.is_igst,
        notes=f"Credit Note against {original.invoice_no}. Reason: {reason}",
        status='sent',
        created_by=current_user.id
    )
    db.session.add(cn)
    db.session.flush()
    
    for item in original.items:
        cn_item = InvoiceItem(
            invoice_id=cn.id,
            item_id=item.item_id,
            description=item.description,
            hsn_sac=item.hsn_sac,
            qty=item.qty,
            unit=item.unit,
            rate=item.rate,
            discount_pct=item.discount_pct,
            gst_rate=item.gst_rate,
            cess_rate=item.cess_rate,
            sort_order=item.sort_order
        )
        cn_item.calculate(is_igst=cn.is_igst)
        db.session.add(cn_item)
    
    db.session.flush()
    cn.calculate_totals()
    db.session.commit()
    flash(f'Credit Note {cn.invoice_no} created!', 'success')
    return redirect(url_for('invoices.view', id=cn.id))


# ─── PROFORMA → TAX INVOICE CONVERSION ─────────────────────
@invoices_bp.route('/invoices/<int:id>/convert-to-tax', methods=['POST'])
@login_required
def convert_to_tax(id):
    inv = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    if inv.invoice_type != 'proforma':
        flash('Only Proforma Invoices can be converted.', 'danger')
        return redirect(url_for('invoices.view', id=id))
    inv.invoice_type = 'tax_invoice'
    # Re-number with new Tax Invoice number
    org = Organization.query.get(org_id())
    inv.invoice_no = get_next_invoice_no(org)
    inv.invoice_date = date.today()
    org.invoice_count_this_month = (org.invoice_count_this_month or 0) + 1
    db.session.commit()
    flash(f'✅ Converted to Tax Invoice {inv.invoice_no}!', 'success')
    return redirect(url_for('invoices.view', id=id))


# ─── BULK OPERATIONS ────────────────────────────────────────
@invoices_bp.route('/invoices/bulk-action', methods=['POST'])
@login_required
def bulk_action():
    action = request.form.get('action')
    ids = request.form.getlist('ids[]')
    if not ids:
        flash('No invoices selected.', 'warning')
        return redirect(url_for('invoices.list'))

    invoices = Invoice.query.filter(
        Invoice.id.in_([int(i) for i in ids]),
        Invoice.org_id == org_id()
    ).all()

    if action == 'delete':
        for inv in invoices:
            if inv.status == 'draft':
                db.session.delete(inv)
        db.session.commit()
        flash(f'Deleted {len(invoices)} draft invoice(s).', 'success')

    elif action == 'mark_sent':
        for inv in invoices:
            if inv.status == 'draft':
                inv.status = 'sent'
        db.session.commit()
        flash(f'Marked {len(invoices)} invoice(s) as Sent.', 'success')

    elif action == 'mark_paid':
        for inv in invoices:
            if inv.status in ['sent', 'partial']:
                inv.status = 'paid'
                inv.amount_paid = inv.grand_total
                inv.balance_due = 0
        db.session.commit()
        flash(f'Marked {len(invoices)} invoice(s) as Paid.', 'success')

    elif action == 'send_reminder':
        count = 0
        for inv in invoices:
            if inv.customer.email and inv.status in ['sent', 'partial']:
                try:
                    _send_payment_reminder(inv)
                    count += 1
                except Exception:
                    pass
        db.session.commit()
        flash(f'Payment reminders sent to {count} customer(s).', 'success')

    return redirect(url_for('invoices.list'))


def _send_payment_reminder(invoice):
    """Internal helper: send a payment reminder email for an invoice."""
    from flask_mail import Message
    from extensions import mail
    org = Organization.query.get(invoice.org_id)
    customer = invoice.customer
    if not customer.email:
        return

    days_overdue = (date.today() - invoice.due_date).days if invoice.due_date else 0
    if days_overdue > 0:
        subject = f'⚠️ Payment Overdue — {invoice.invoice_no} ({days_overdue} days)'
        urgency = f'Your payment is now {days_overdue} day(s) overdue.'
    elif days_overdue == 0:
        subject = f'📅 Payment Due Today — {invoice.invoice_no}'
        urgency = 'Your payment is due today.'
    else:
        subject = f'🔔 Payment Reminder — {invoice.invoice_no}'
        urgency = f'Your payment is due on {invoice.due_date.strftime("%d %b %Y")}.'

    msg = Message(
        subject=subject,
        sender=f'{org.name} <{org.email or "noreply@billflowpro.com"}>',
        recipients=[customer.email]
    )
    msg.body = f"""Dear {customer.name},

This is a friendly reminder regarding your outstanding invoice.

Invoice No : {invoice.invoice_no}
Invoice Date: {invoice.invoice_date.strftime('%d %b %Y')}
Due Date   : {invoice.due_date.strftime('%d %b %Y') if invoice.due_date else 'N/A'}
Amount Due : ₹{float(invoice.balance_due):,.2f}

{urgency}

Please arrange payment at the earliest.

For any queries, please contact us.

Regards,
{org.name}
{org.phone or ''}
{org.email or ''}
"""
    mail.send(msg)
    invoice.last_reminder_sent = datetime.utcnow()


# ─── PAYMENT REMINDERS SCHEDULER ENDPOINT ───────────────────
@invoices_bp.route('/invoices/run-reminders')
@login_required
def run_reminders():
    """Manually trigger all scheduled payment reminders for this org."""
    org = Organization.query.get(org_id())
    today = date.today()
    sent = 0
    errors = 0

    overdue_invoices = Invoice.query.filter_by(org_id=org_id()).filter(
        Invoice.status.in_(['sent', 'partial']),
        Invoice.due_date != None
    ).all()

    for inv in overdue_invoices:
        if not inv.customer.email:
            continue
        days = (today - inv.due_date).days
        should_send = (
            (org.reminder_before_due and days == -3) or
            (org.reminder_on_due and days == 0) or
            (org.reminder_after_due and days == 7)
        )
        if should_send:
            try:
                _send_payment_reminder(inv)
                sent += 1
            except Exception:
                errors += 1

    db.session.commit()
    flash(f'✅ Reminders sent: {sent}. Errors: {errors}.', 'success' if errors == 0 else 'warning')
    return redirect(url_for('invoices.list'))
