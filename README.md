# BillFlow Pro 💼

**Industry-Level Multi-Tenant SaaS Billing System** — Zoho Books jaisa, lekin aapka khud ka!

## 🚀 Quick Start

### 1. Install & Run (Windows)

```bash
# Option A: Double-click start.bat in backend/ folder
# Option B: Command line:
cd "d:\New folder (7)\billflow-pro\backend"
pip install -r requirements.txt
python app.py
```

Open browser: **http://localhost:5000**

### 2. First Steps
1. Register your company at `/register`
2. Complete company setup (GSTIN, logo, bank details)
3. Add items/products to catalog
4. Add customers
5. Create your first invoice!

---

## 📁 Project Structure

```
billflow-pro/
├── backend/
│   ├── app.py              ← Main Flask app (start here)
│   ├── config.py           ← Database, mail settings
│   ├── extensions.py       ← Flask extensions
│   ├── .env                ← ⚠️ Edit this! Add your credentials
│   ├── requirements.txt
│   ├── start.bat           ← Windows one-click start
│   ├── models/             ← Database models (SQLAlchemy)
│   │   ├── organization.py ← Multi-tenant company model
│   │   ├── user.py         ← Auth + roles
│   │   ├── customer.py
│   │   ├── vendor.py
│   │   ├── item.py
│   │   ├── invoice.py      ← Invoice + InvoiceItem with GST calc
│   │   ├── payment.py
│   │   └── quotation.py
│   ├── routes/             ← Flask blueprints
│   │   ├── auth.py         ← Login, Register, Logout
│   │   ├── dashboard.py    ← KPIs, charts
│   │   ├── customers.py    ← CRUD + API search
│   │   ├── items.py        ← Product catalog
│   │   ├── invoices.py     ← Create, view, PDF, payment
│   │   ├── quotations.py   ← Quotes → Invoice conversion
│   │   ├── reports.py      ← Sales register, GSTR-1
│   │   └── settings.py     ← Company profile
│   └── utils/
│       ├── gst_calculator.py  ← Tax calculation, Indian states
│       ├── pdf_generator.py   ← WeasyPrint PDF
│       └── email_sender.py    ← Invoice email
│
└── frontend/
    ├── templates/           ← Jinja2 HTML templates
    │   ├── base.html        ← Dark sidebar layout
    │   ├── auth/            ← Login, Register pages
    │   ├── dashboard/       ← KPI dashboard with Chart.js
    │   ├── invoices/        ← Create, view, list, PDF
    │   ├── customers/       ← List, add, detail
    │   ├── items/           ← Product catalog
    │   ├── quotations/      ← Quotes with convert-to-invoice
    │   ├── reports/         ← Sales register, GSTR-1
    │   └── settings/        ← Company settings + setup wizard
    └── static/
        ├── css/style.css    ← Dark premium design system
        └── js/
            ├── main.js              ← Global UI
            └── invoice_builder.js  ← Dynamic line items + GST calc
```

---

## ⚙️ Configuration (.env)

```env
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///billflow_dev.db       # SQLite for dev
# DATABASE_URL=postgresql://...              # PostgreSQL for production
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your-app-password
CLOUDINARY_CLOUD_NAME=...                   # For logo upload
```

---

## 🎯 Features Implemented (Phase 1-4)

### ✅ Multi-Tenant Architecture
- Each company = separate isolated account
- Role-based access: Owner / Admin / Accountant / Viewer

### ✅ Authentication
- Company registration with auto owner user creation
- Login/logout with remember me
- Onboarding wizard after signup

### ✅ Dashboard
- Total revenue, monthly revenue, outstanding, overdue
- Revenue trend chart (Chart.js)
- Top customers by revenue
- Recent invoices table

### ✅ Invoice Engine
- Dynamic line items (add/remove rows via JS)
- Auto GST calc: CGST+SGST (intra) / IGST (inter-state)
- Item autocomplete from catalog
- Per-item discount + GST rate
- Amount in words (Indian format)
- PDF download (WeasyPrint)
- Status: Draft → Sent → Partial → Paid → Cancelled
- Payment recording (Cash/Bank/UPI/Cheque/NEFT)

### ✅ Quotations
- Same interface as invoice
- One-click convert to invoice

### ✅ Customers
- Full GST details (GSTIN, state code)
- Billing + shipping address
- Outstanding balance calculation
- Customer ledger (invoice history)

### ✅ Items/Products
- HSN/SAC codes
- GST rate (0/5/12/18/28%)
- Selling + purchase price
- Goods vs Service classification

### ✅ Reports
- Sales register (date-wise with GST columns)
- GSTR-1 summary (B2B + B2C split)

### ✅ Settings
- Company profile, logo upload (Cloudinary)
- GSTIN, PAN, bank details
- Invoice prefix, starting number
- Default notes and terms

---

## 🗺️ Remaining Phases (Next Steps)

- **Phase 5**: Vendors, Purchase Orders, Delivery Challan
- **Phase 6**: Profit & Loss, Cash book, Excel export
- **Phase 7**: Subscription plans, Super Admin panel
- **Phase 8**: Deployment on Render/Railway

---

## 🔒 Multi-Tenant Security

Every DB query filters by `org_id = current_user.org_id` — 
Company A can NEVER see Company B's data.
