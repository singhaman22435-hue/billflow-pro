
def format_currency(amount):
    """Format number as Indian currency"""
    try:
        amount = float(amount)
        # Indian number format
        s = f"{amount:.2f}"
        parts = s.split('.')
        x = parts[0]
        last3 = x[-3:]
        rest = x[:-3]
        if rest:
            formatted = ','.join([rest[max(i-2,0):i] for i in range(len(rest), 0, -2)][::-1]) + ',' + last3
        else:
            formatted = last3
        return f"₹{formatted}.{parts[1]}"
    except:
        return f"₹{amount}"

def gst_calculate(taxable_amount, gst_rate, is_igst=False):
    """Calculate GST components"""
    taxable = float(taxable_amount)
    rate = float(gst_rate)
    if is_igst:
        return {'igst': round(taxable * rate / 100, 2), 'cgst': 0, 'sgst': 0}
    else:
        half = rate / 2
        return {
            'igst': 0,
            'cgst': round(taxable * half / 100, 2),
            'sgst': round(taxable * half / 100, 2)
        }

def amount_to_words(amount):
    """Convert amount to words (Indian format)"""
    try:
        from num2words import num2words
        rupees = int(amount)
        paise = round((float(amount) - rupees) * 100)
        words = num2words(rupees, lang='en_IN').title()
        if paise > 0:
            paise_words = num2words(paise, lang='en_IN').title()
            return f"{words} Rupees And {paise_words} Paise Only"
        return f"{words} Rupees Only"
    except Exception:
        return f"Rupees {amount}"

INDIAN_STATES = [
    ('01', 'Jammu & Kashmir'), ('02', 'Himachal Pradesh'), ('03', 'Punjab'),
    ('04', 'Chandigarh'), ('05', 'Uttarakhand'), ('06', 'Haryana'),
    ('07', 'Delhi'), ('08', 'Rajasthan'), ('09', 'Uttar Pradesh'),
    ('10', 'Bihar'), ('11', 'Sikkim'), ('12', 'Arunachal Pradesh'),
    ('13', 'Nagaland'), ('14', 'Manipur'), ('15', 'Mizoram'),
    ('16', 'Tripura'), ('17', 'Meghalaya'), ('18', 'Assam'),
    ('19', 'West Bengal'), ('20', 'Jharkhand'), ('21', 'Odisha'),
    ('22', 'Chhattisgarh'), ('23', 'Madhya Pradesh'), ('24', 'Gujarat'),
    ('25', 'Daman & Diu'), ('26', 'Dadra & Nagar Haveli'), ('27', 'Maharashtra'),
    ('28', 'Andhra Pradesh'), ('29', 'Karnataka'), ('30', 'Goa'),
    ('31', 'Lakshadweep'), ('32', 'Kerala'), ('33', 'Tamil Nadu'),
    ('34', 'Puducherry'), ('35', 'Andaman & Nicobar'), ('36', 'Telangana'),
    ('37', 'Andhra Pradesh (New)'), ('38', 'Ladakh')
]
