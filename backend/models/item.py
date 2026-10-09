from extensions import db
from datetime import datetime

class Item(db.Model):
    __tablename__ = 'items'
    __table_args__ = (
        db.Index('idx_item_org_active', 'org_id', 'is_active'),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    hsn_sac = db.Column(db.String(20))
    item_type = db.Column(db.String(20), default='goods')  # goods/service
    category = db.Column(db.String(100))  # e.g. "Electronics", "Services"
    unit = db.Column(db.String(20), default='Nos')  # Nos, Kg, Ltr, Mtr, etc.
    selling_price = db.Column(db.Numeric(15, 2), default=0)
    purchase_price = db.Column(db.Numeric(15, 2), default=0)
    gst_rate = db.Column(db.Numeric(5, 2), default=18)  # 0,5,12,18,28
    cess_rate = db.Column(db.Numeric(5, 2), default=0)
    opening_stock = db.Column(db.Numeric(10, 2), default=0)

    # ── Inventory Tracking ──────────────────────────
    track_inventory = db.Column(db.Boolean, default=False)
    current_stock = db.Column(db.Numeric(10, 2), default=0)
    min_stock_level = db.Column(db.Numeric(10, 2), default=0)  # Low stock alert threshold
    max_stock_level = db.Column(db.Numeric(10, 2), default=0)
    warehouse_location = db.Column(db.String(100))  # e.g. "Shelf A3"

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Item {self.name}>'

    @property
    def is_low_stock(self):
        if not self.track_inventory:
            return False
        return float(self.current_stock or 0) <= float(self.min_stock_level or 0)

    @property
    def stock_status(self):
        if not self.track_inventory:
            return 'not_tracked'
        stock = float(self.current_stock or 0)
        min_s = float(self.min_stock_level or 0)
        if stock <= 0:
            return 'out_of_stock'
        elif stock <= min_s:
            return 'low_stock'
        return 'in_stock'

