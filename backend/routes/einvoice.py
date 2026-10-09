from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from extensions import db
from models.invoice import Invoice
from models.organization import Organization
from datetime import datetime
import json
import io

einvoice_bp = Blueprint('einvoice', __name__)

def org_id():
    return current_user.org_id

# ─── E-INVOICE JSON GENERATOR ─────────────────────────────
def build_einvoice_json(invoice, org):
    """Generate E-Invoice JSON as per GST IRP NIC schema v1.1"""
    items_list = []
    for idx, item in enumerate(invoice.items, 1):
        items_list.append({
            "SlNo": str(idx),
            "PrdDesc": item.description or "Goods/Services",
            "IsServc": "N",  # Y for service, N for goods
            "HsnCd": item.hsn_sac or "9999",
            "Qty": float(item.qty or 1),
            "Unit": (item.unit or "NOS").upper()[:3],
            "UnitPrice": float(item.rate or 0),
            "TotAmt": float(item.amount or 0),
            "Discount": float(item.discount_amount or 0),
            "AssAmt": float(item.taxable_amount or 0),
            "GstRt": float(item.gst_rate or 0),
            "IgstAmt": float(item.igst_amount or 0),
            "CgstAmt": float(item.cgst_amount or 0),
            "SgstAmt": float(item.sgst_amount or 0),
            "CesRt": float(item.cess_rate or 0),
            "CesAmt": float(item.cess_amount or 0),
            "TotItemVal": float(item.taxable_amount or 0) + float(item.cgst_amount or 0) + float(item.sgst_amount or 0) + float(item.igst_amount or 0)
        })

    customer = invoice.customer
    einv = {
        "Version": "1.1",
        "TranDtls": {
            "TaxSch": "GST",
            "SupTyp": "B2B",
            "RegRev": "N",
            "EcmGstin": None,
            "IgstOnIntra": "N"
        },
        "DocDtls": {
            "Typ": "INV",
            "No": invoice.invoice_no,
            "Dt": invoice.invoice_date.strftime("%d/%m/%Y")
        },
        "SellerDtls": {
            "Gstin": org.gstin or "",
            "LglNm": org.legal_name or org.name,
            "TrdNm": org.name,
            "Addr1": org.address_line1 or "",
            "Addr2": org.address_line2 or "",
            "Loc": org.city or "",
            "Pin": int(org.pincode or 0),
            "Stcd": org.state_code or "27",
            "Ph": org.phone or "",
            "Em": org.email or ""
        },
        "BuyerDtls": {
            "Gstin": customer.gstin or "URP",
            "LglNm": customer.name,
            "TrdNm": customer.company_name or customer.name,
            "Pos": invoice.place_of_supply or org.state_code or "27",
            "Addr1": customer.address or "",
            "Addr2": "",
            "Loc": customer.city or "",
            "Pin": int(customer.pincode or 0) if customer.pincode else 0,
            "Stcd": customer.state_code or "27",
            "Ph": customer.phone or "",
            "Em": customer.email or ""
        },
        "ItemList": items_list,
        "ValDtls": {
            "AssVal": float(invoice.taxable_amount or 0),
            "CgstVal": float(invoice.cgst_amount or 0),
            "SgstVal": float(invoice.sgst_amount or 0),
            "IgstVal": float(invoice.igst_amount or 0),
            "CesVal": float(invoice.cess_amount or 0),
            "Discount": float(invoice.total_discount or 0),
            "RndOffAmt": float(invoice.round_off or 0),
            "TotInvVal": float(invoice.grand_total or 0)
        }
    }
    return einv


@einvoice_bp.route('/invoices/<int:id>/e-invoice', methods=['GET', 'POST'])
@login_required
def einvoice(id):
    invoice = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_irn':
            # Manual IRN entry (user got IRN from GSP/IRP portal)
            invoice.irn = request.form.get('irn', '').strip()
            invoice.ack_no = request.form.get('ack_no', '').strip()
            ack_date_str = request.form.get('ack_date', '')
            if ack_date_str:
                try:
                    invoice.ack_date = datetime.strptime(ack_date_str, '%Y-%m-%dT%H:%M')
                except Exception:
                    invoice.ack_date = datetime.utcnow()
            db.session.commit()
            flash('✅ E-Invoice IRN saved successfully!', 'success')
            return redirect(url_for('einvoice.einvoice', id=id))

        elif action == 'download_json':
            einv_json = build_einvoice_json(invoice, org)
            json_str = json.dumps(einv_json, indent=2, ensure_ascii=False)
            return send_file(
                io.BytesIO(json_str.encode('utf-8')),
                mimetype='application/json',
                as_attachment=True,
                download_name=f'einvoice_{invoice.invoice_no}.json'
            )

        elif action == 'cancel_irn':
            invoice.irn = None
            invoice.ack_no = None
            invoice.ack_date = None
            invoice.qr_code_data = None
            db.session.commit()
            flash('E-Invoice IRN cleared.', 'info')
            return redirect(url_for('einvoice.einvoice', id=id))

    einv_json = build_einvoice_json(invoice, org)
    return render_template('einvoice/einvoice.html',
                           invoice=invoice, org=org,
                           einv_json=json.dumps(einv_json, indent=2, ensure_ascii=False))


# ─── E-WAY BILL ───────────────────────────────────────────
@einvoice_bp.route('/invoices/<int:id>/e-way-bill', methods=['GET', 'POST'])
@login_required
def ewaybill(id):
    invoice = Invoice.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_ewb':
            invoice.ewb_no = request.form.get('ewb_no', '').strip()
            db.session.commit()
            flash('✅ E-Way Bill number saved!', 'success')
            return redirect(url_for('einvoice.ewaybill', id=id))

        elif action == 'download_json':
            # Build E-Way Bill JSON (NIC format)
            customer = invoice.customer
            ewb_data = {
                "supplyType": "O",  # Outward
                "subSupplyType": "1",  # Supply
                "docType": "INV",
                "docNo": invoice.invoice_no,
                "docDate": invoice.invoice_date.strftime("%d/%m/%Y"),
                "fromGstin": org.gstin or "",
                "fromTrdName": org.name,
                "fromAddr1": org.address_line1 or "",
                "fromAddr2": org.address_line2 or "",
                "fromPlace": org.city or "",
                "fromPincode": int(org.pincode or 0),
                "fromStateCode": int(org.state_code or 27),
                "toGstin": customer.gstin or "URP",
                "toTrdName": customer.name,
                "toAddr1": customer.address or "",
                "toAddr2": "",
                "toPlace": customer.city or "",
                "toPincode": int(customer.pincode or 0) if customer.pincode else 0,
                "toStateCode": int(customer.state_code or 27),
                "transactionType": 1,
                "dispatchFromGSTIN": org.gstin or "",
                "dispatchFromTradeName": org.name,
                "shipToGSTIN": customer.gstin or "URP",
                "shipToTradeName": customer.name,
                "totalValue": float(invoice.taxable_amount or 0),
                "cgstValue": float(invoice.cgst_amount or 0),
                "sgstValue": float(invoice.sgst_amount or 0),
                "igstValue": float(invoice.igst_amount or 0),
                "cessValue": float(invoice.cess_amount or 0),
                "totInvValue": float(invoice.grand_total or 0),
                "transMode": request.form.get('trans_mode', '1'),
                "transDistance": request.form.get('distance', ''),
                "transporterName": request.form.get('transporter_name', ''),
                "transporterId": request.form.get('transporter_gstin', ''),
                "transDocNo": request.form.get('lr_no', ''),
                "transDocDate": request.form.get('lr_date', ''),
                "vehicleNo": request.form.get('vehicle_no', ''),
                "vehicleType": request.form.get('vehicle_type', 'R'),
                "itemList": [
                    {
                        "productName": item.description,
                        "hsnCode": item.hsn_sac or "9999",
                        "productDesc": item.description,
                        "quantity": float(item.qty or 1),
                        "qtyUnit": (item.unit or "NOS").upper()[:3],
                        "taxableAmount": float(item.taxable_amount or 0),
                        "cgstRate": float(item.cgst_rate or 0),
                        "sgstRate": float(item.sgst_rate or 0),
                        "igstRate": float(item.igst_rate or 0),
                        "cessRate": float(item.cess_rate or 0)
                    } for item in invoice.items
                ]
            }
            json_str = json.dumps(ewb_data, indent=2, ensure_ascii=False)
            return send_file(
                io.BytesIO(json_str.encode('utf-8')),
                mimetype='application/json',
                as_attachment=True,
                download_name=f'ewaybill_{invoice.invoice_no}.json'
            )

    return render_template('einvoice/ewaybill.html', invoice=invoice, org=org)
