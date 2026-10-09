from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.item import Item

items_bp = Blueprint('items', __name__)

def org_id():
    return current_user.org_id

@items_bp.route('/items')
@login_required
def list():
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    export = request.args.get('export', '')

    query = Item.query.filter_by(org_id=org_id(), is_active=True)
    if search:
        query = query.filter(Item.name.ilike(f'%{search}%'))
    
    query = query.order_by(Item.name)

    if export == 'csv':
        items = query.all()
        import io, csv
        from flask import make_response
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Name', 'Description', 'HSN/SAC', 'Unit', 'Selling Price', 'GST Rate'])
        for i in items:
            cw.writerow([i.name, i.description or '', i.hsn_sac or '', i.unit or '', i.selling_price, i.gst_rate])
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=items.csv"
        output.headers["Content-type"] = "text/csv"
        return output

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    items = pagination.items
    return render_template('items/list.html', items=items, pagination=pagination, search=search)

@items_bp.route('/items/import', methods=['POST'])
@login_required
def import_csv():
    if 'file' not in request.files:
        flash('No file uploaded.', 'danger')
        return redirect(url_for('items.list'))
        
    file = request.files['file']
    if file.filename == '':
        flash('No selected file.', 'danger')
        return redirect(url_for('items.list'))
        
    if file and file.filename.endswith('.csv'):
        import csv
        import io
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        count = 0
        for row in csv_input:
            # Requires at least a 'Name' column
            name = row.get('Name', '').strip()
            if not name:
                continue
                
            selling_price = 0
            try:
                selling_price = float(row.get('Selling Price', 0) or 0)
            except: pass
            
            gst_rate = 18
            try:
                gst_rate = float(row.get('GST Rate', 18) or 18)
            except: pass
                
            item = Item(
                org_id=org_id(),
                name=name,
                description=row.get('Description', ''),
                hsn_sac=row.get('HSN/SAC', ''),
                unit=row.get('Unit', 'Nos'),
                selling_price=selling_price,
                gst_rate=gst_rate
            )
            db.session.add(item)
            count += 1
            
        db.session.commit()
        flash(f'Successfully imported {count} items.', 'success')
    else:
        flash('Please upload a valid CSV file.', 'danger')
        
    return redirect(url_for('items.list'))

@items_bp.route('/items/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        item = Item(
            org_id=org_id(),
            name=request.form.get('name'),
            description=request.form.get('description'),
            hsn_sac=request.form.get('hsn_sac'),
            item_type=request.form.get('item_type', 'goods'),
            unit=request.form.get('unit', 'Nos'),
            selling_price=request.form.get('selling_price') or 0,
            purchase_price=request.form.get('purchase_price') or 0,
            gst_rate=request.form.get('gst_rate') or 18,
            cess_rate=request.form.get('cess_rate') or 0,
        )
        db.session.add(item)
        db.session.commit()
        flash('Item added!', 'success')
        return redirect(url_for('items.list'))
    return render_template('items/add.html')

@items_bp.route('/items/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    item = Item.query.filter_by(id=id, org_id=org_id()).first_or_404()
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.description = request.form.get('description')
        item.hsn_sac = request.form.get('hsn_sac')
        item.item_type = request.form.get('item_type', 'goods')
        item.unit = request.form.get('unit', 'Nos')
        item.selling_price = request.form.get('selling_price') or 0
        item.purchase_price = request.form.get('purchase_price') or 0
        item.gst_rate = request.form.get('gst_rate') or 18
        item.cess_rate = request.form.get('cess_rate') or 0
        db.session.commit()
        flash('Item updated!', 'success')
        return redirect(url_for('items.list'))
    return render_template('items/add.html', item=item)

@items_bp.route('/items/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    item = Item.query.filter_by(id=id, org_id=org_id()).first_or_404()
    item.is_active = False
    db.session.commit()
    flash('Item deleted.', 'info')
    return redirect(url_for('items.list'))

@items_bp.route('/api/items/search')
@login_required
def api_search():
    q = request.args.get('q', '')
    items = Item.query.filter_by(org_id=org_id(), is_active=True).filter(
        Item.name.ilike(f'%{q}%')
    ).limit(10).all()
    return jsonify([{
        'id': i.id, 'name': i.name, 'hsn_sac': i.hsn_sac or '',
        'unit': i.unit, 'selling_price': float(i.selling_price),
        'gst_rate': float(i.gst_rate), 'cess_rate': float(i.cess_rate),
        'description': i.description or ''
    } for i in items])
