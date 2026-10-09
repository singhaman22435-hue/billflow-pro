from flask import render_template
from xhtml2pdf import pisa
import io

def generate_invoice_pdf(invoice, org):
    """Generate PDF from invoice using xhtml2pdf"""
    from utils.gst_calculator import amount_to_words, format_currency
    
    html_content = render_template(
        'invoices/pdf_template.html',
        invoice=invoice,
        org=org,
        amount_in_words=amount_to_words(float(invoice.grand_total)),
        format_currency=format_currency
    )
    
    result = io.BytesIO()
    # Create PDF
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=result)
    
    if pisa_status.err:
        raise Exception('PDF generation failed')
        
    return result.getvalue()

def generate_po_pdf(po, org):
    """Generate PDF from purchase order using xhtml2pdf"""
    from utils.gst_calculator import amount_to_words, format_currency
    
    html_content = render_template(
        'purchase_orders/pdf_template.html',
        po=po,
        org=org,
        amount_in_words=amount_to_words(float(po.grand_total or 0)),
        format_currency=format_currency
    )
    
    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=result)
    
    if pisa_status.err:
        raise Exception('PO PDF generation failed')
        
    return result.getvalue()

def generate_quotation_pdf(qt, org):
    """Generate PDF from quotation using xhtml2pdf"""
    from utils.gst_calculator import amount_to_words, format_currency
    
    html_content = render_template(
        'quotations/pdf_template.html',
        qt=qt,
        org=org,
        amount_in_words=amount_to_words(float(qt.grand_total or 0)),
        format_currency=format_currency
    )
    
    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=result)
    
    if pisa_status.err:
        raise Exception('Quotation PDF generation failed')
        
    return result.getvalue()

def generate_dc_pdf(dc, org):
    """Generate PDF from delivery challan using xhtml2pdf"""
    from utils.gst_calculator import format_currency
    
    html_content = render_template(
        'delivery_challans/pdf_template.html',
        dc=dc,
        org=org,
        format_currency=format_currency
    )
    
    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=result)
    
    if pisa_status.err:
        raise Exception('DC PDF generation failed')
        
    return result.getvalue()

def generate_payslip_pdf(ps, org):
    """Generate PDF from payslip using xhtml2pdf"""
    from utils.gst_calculator import format_currency

    html_content = render_template(
        'payroll/payslip_pdf.html',
        ps=ps,
        org=org,
        format_currency=format_currency
    )

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=result)

    if pisa_status.err:
        raise Exception('Payslip PDF generation failed')

    return result.getvalue()
