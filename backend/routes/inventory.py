from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.item import Item
from models.organization import Organization
import json

inventory_bp = Blueprint('inventory', __name__)

def org_id():
    return current_user.org_id

# ─── STOCK DASHBOARD ──────────────────────────────────────
@inventory_bp.route('/inventory')
@login_required
def index():
    items = Item.query.filter_by(org_id=org_id(), is_active=True, track_inventory=True)\
        .order_by(Item.name).all()
    low_stock = [i for i in items if i.is_low_stock]
    out_of_stock = [i for i in items if float(i.current_stock or 0) <= 0]
    return render_template('inventory/index.html',
                           items=items, low_stock=low_stock,
                           out_of_stock=out_of_stock)

# ─── ADJUST STOCK ─────────────────────────────────────────
@inventory_bp.route('/inventory/<int:id>/adjust', methods=['POST'])
@login_required
def adjust(id):
    item = Item.query.filter_by(id=id, org_id=org_id()).first_or_404()
    adj_type = request.form.get('type')  # add / remove / set
    try:
        qty = float(request.form.get('qty') or 0)
    except (ValueError, TypeError):
        qty = 0

    if adj_type == 'add':
        item.current_stock = float(item.current_stock or 0) + qty
    elif adj_type == 'remove':
        item.current_stock = max(0, float(item.current_stock or 0) - qty)
    elif adj_type == 'set':
        item.current_stock = qty

    db.session.commit()
    flash(f'Stock updated for {item.name}: {item.current_stock} {item.unit}', 'success')
    return redirect(url_for('inventory.index'))

# ─── ENABLE TRACKING on item ──────────────────────────────
@inventory_bp.route('/inventory/<int:id>/enable', methods=['POST'])
@login_required
def enable(id):
    item = Item.query.filter_by(id=id, org_id=org_id()).first_or_404()
    item.track_inventory = True
    try:
        item.current_stock = float(request.form.get('opening_stock') or item.opening_stock or 0)
    except (ValueError, TypeError):
        item.current_stock = 0
    try:
        item.min_stock_level = float(request.form.get('min_stock') or 0)
    except (ValueError, TypeError):
        item.min_stock_level = 0
    item.warehouse_location = request.form.get('location', '')
    db.session.commit()
    flash(f'Inventory tracking enabled for {item.name}!', 'success')
    return redirect(url_for('inventory.index'))

# ─── LOW STOCK API ────────────────────────────────────────
@inventory_bp.route('/api/inventory/low-stock')
@login_required
def api_low_stock():
    items = Item.query.filter_by(org_id=org_id(), is_active=True, track_inventory=True).all()
    low = [{'id': i.id, 'name': i.name, 'stock': float(i.current_stock or 0),
            'min': float(i.min_stock_level or 0), 'unit': i.unit,
            'status': i.stock_status} for i in items if i.is_low_stock]
    return jsonify(low)
