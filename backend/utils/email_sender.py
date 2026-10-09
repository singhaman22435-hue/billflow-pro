from flask_mail import Message
from extensions import mail
from flask import render_template

def send_invoice_email(invoice, org, recipient_email, recipient_name, pdf_bytes=None, custom_message=None):
    """Send invoice via email with PDF attachment"""
    subject = f"Invoice {invoice.invoice_no} from {org.name}"
    body = custom_message or f"""Dear {recipient_name},

Please find attached your invoice {invoice.invoice_no} for ₹{float(invoice.grand_total):,.2f}.

Due Date: {invoice.due_date.strftime('%d %b %Y') if invoice.due_date else 'As discussed'}

Thank you for your business!

Regards,
{org.name}
"""
    msg = Message(
        subject=subject,
        recipients=[recipient_email],
        body=body
    )
    
    if pdf_bytes:
        msg.attach(
            filename=f'{invoice.invoice_no}.pdf',
            content_type='application/pdf',
            data=pdf_bytes
        )
    
    mail.send(msg)
    return True
