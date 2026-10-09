from extensions import db
from datetime import date
from dateutil.relativedelta import relativedelta
from models.recurring_invoice import RecurringInvoice
from models.invoice import Invoice, InvoiceItem
from models.customer import Customer
from models.organization import Organization
from flask import current_app
from routes.invoices import get_next_invoice_no
import logging

def process_recurring_invoices(app):
    with app.app_context():
        today = date.today()
        logging.info(f"Running recurring invoice job for {today}...")

        # Find all active recurring invoices that are due today or earlier
        due_recurrings = RecurringInvoice.query.filter(
            RecurringInvoice.is_active == True,
            RecurringInvoice.status == 'active',
            RecurringInvoice.next_date <= today
        ).all()

        count = 0
        for r in due_recurrings:
            org = Organization.query.get(r.org_id)
            if not org or not org.can_create_invoice():
                continue # Skip if org limit reached
                
            # Create the invoice
            inv = Invoice(
                org_id=r.org_id,
                customer_id=r.customer_id,
                invoice_no=get_next_invoice_no(org),
                invoice_type='tax_invoice',
                invoice_date=today,
                due_date=today + relativedelta(days=7), # Default 7 days
                place_of_supply=r.place_of_supply,
                is_igst=r.is_igst,
                notes=r.notes,
                terms=r.terms,
                status='sent' if r.auto_send_email else 'draft',
                created_by=r.created_by
            )
            db.session.add(inv)
            db.session.flush()

            for i, rit in enumerate(r.items):
                inv_item = InvoiceItem(
                    invoice_id=inv.id,
                    item_id=rit.item_id,
                    description=rit.description,
                    hsn_sac=rit.hsn_sac,
                    qty=rit.qty,
                    unit=rit.unit,
                    rate=rit.rate,
                    discount_pct=rit.discount_pct,
                    gst_rate=rit.gst_rate,
                    cess_rate=rit.cess_rate,
                    sort_order=i
                )
                inv_item.calculate(is_igst=r.is_igst)
                db.session.add(inv_item)
                
                # Handle inventory
                if inv_item.item_id:
                    from models.item import Item
                    item = Item.query.get(inv_item.item_id)
                    if item and item.track_inventory:
                        item.current_stock = float(item.current_stock or 0) - float(inv_item.qty or 0)

            db.session.flush()
            inv.calculate_totals()
            org.invoice_count_this_month += 1
            
            # Move next_date forward
            if r.frequency == 'weekly':
                r.next_date = today + relativedelta(weeks=1)
            elif r.frequency == 'monthly':
                r.next_date = today + relativedelta(months=1)
            elif r.frequency == 'yearly':
                r.next_date = today + relativedelta(years=1)
            
            # Check end_date
            if r.end_date and r.next_date > r.end_date:
                r.status = 'completed'
                r.is_active = False
                
            db.session.commit()
            count += 1
            
            # Send Email if required
            if r.auto_send_email and inv.customer.email:
                try:
                    from utils.pdf_generator import generate_invoice_pdf
                    from extensions import mail
                    from flask_mail import Message
                    pdf_bytes = generate_invoice_pdf(inv, org)
                    msg = Message(
                        subject=f"Invoice {inv.invoice_no} from {org.name}",
                        sender=app.config.get('MAIL_DEFAULT_SENDER'),
                        recipients=[inv.customer.email]
                    )
                    msg.body = f"Dear {inv.customer.name},\n\nPlease find attached the invoice {inv.invoice_no} for the amount {inv.grand_total}.\n\nRegards,\n{org.name}"
                    msg.attach(f"{inv.invoice_no}.pdf", "application/pdf", pdf_bytes)
                    mail.send(msg)
                except Exception as e:
                    logging.error(f"Failed to auto-send email for {inv.invoice_no}: {str(e)}")

        logging.info(f"Generated {count} recurring invoices.")
