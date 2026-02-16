# 🖨️ PrintBill Pro
### Professional Printer Billing Management System

---

## 📁 Project Structure

```
printer_billing/
├── main.py                     # 🚀 Entry point — run this
├── requirements.txt
├── printbill.db                # SQLite database (auto-created)
│
├── database/
│   ├── connection.py           # All DB access + CRUD (single source of truth)
│   └── __init__.py
│
├── services/
│   ├── billing_service.py      # Bill calculation + invoice logic
│   ├── pdf_service.py          # ReportLab PDF invoice generator
│   └── excel_service.py        # openpyxl Excel exporter
│
├── ui/
│   ├── styles.py               # Qt stylesheet + color palette
│   ├── main_window.py          # Main window + toolbar + tabs
│   ├── dashboard_tab.py        # Stats + recent invoices
│   ├── company_tab.py          # Company CRUD
│   ├── printer_tab.py          # Printer CRUD
│   ├── counter_tab.py          # Monthly counter entry
│   ├── billing_tab.py          # Invoice generation + history
│   └── settings_dialog.py      # App settings
│
├── utils/
│   └── helpers.py              # Pure utility functions
│
├── invoices/                   # Generated PDFs saved here
└── exports/                    # Excel exports saved here
```

---

## 🗄️ Database Schema

```sql
companies (id, name, address, gst_number, rate_per_print,
           contact_person, contact_phone, email)

printers  (id, company_id FK, printer_id, printer_name,
           model, location, is_active)

counter_readings (id, printer_id FK, company_id FK,
                  month, year, opening_counter,
                  closing_counter, total_prints)
                 UNIQUE(printer_id, month, year)

invoices  (id, invoice_number UNIQUE, company_id FK,
           month, year, total_prints, rate_per_print,
           subtotal, cgst_rate, sgst_rate, igst_rate,
           cgst_amount, sgst_amount, igst_amount,
           total_amount, invoice_date, pdf_path, status, notes)
          UNIQUE(company_id, month, year)

invoice_items (id, invoice_id FK, printer_id,
               printer_name, printer_serial, location,
               opening_counter, closing_counter,
               total_prints, rate_per_print, amount)

settings  (key PK, value)
```

---

## ⚡ Setup & Run

```bash
# 1. Clone / unzip the project
cd printer_billing

# 2. Install dependencies
pip install PyQt5 reportlab openpyxl Pillow

# 3. Run
python main.py
```

> **Python 3.10+** required (uses `int | None` union syntax).

---

## 🖥️ Application Tabs

### 1. 🏠 Dashboard
- Live stats: companies, printers, invoices, revenue
- Monthly revenue table for current year
- ⚠️ Alert if any printer has no counter reading this month

### 2. 🏢 Companies
- Add / Edit / Delete companies
- Fields: name, address, GST number, **rate per print**, contact
- Search by name or GST number
- Cascading delete: removes all printers + readings + invoices

### 3. 🖨️ Printers
- Add / Edit / Delete / Toggle Active printers
- Each printer belongs to one company
- Filter by company, search by ID/name/location
- Inactive printers are excluded from billing

### 4. 📊 Counter Entry
- Select Company → Month → Year
- Table auto-loads all **active** printers
- Enter Opening Counter + Closing Counter per printer
- **Total Prints** auto-calculated in real time
- Estimated amount preview at bottom
- Validates closing ≥ opening before saving
- Supports editing saved readings (upsert)

### 5. 🧾 Billing
**Left panel – Generate Bill:**
- Select company, month, year
- Choose GST type: CGST+SGST / IGST / None
- Adjust rates (defaults from Settings)
- Preview shows per-printer breakdown + totals
- Generate creates PDF + saves to DB

**Right panel – Invoice History:**
- Filter by company, year, search
- Open / Download PDF
- Export individual invoice to Excel
- Export all invoices summary to Excel
- Delete invoice (keeps counter readings)

---

## 📄 Invoice PDF Layout

```
┌──────────────────────────────────────────────┐
│  [Logo]  Your Printing Services    TAX INVOICE│
│  Address, Phone, GSTIN         Invoice: INV/  │
│                                Date: 15 Mar   │
│                                Period: Mar 25  │
├──────────────────────────────────────────────┤
│ BILL TO: Acme Corporation                     │
│          123 Main St  |  GSTIN: 27AAB...      │
├──────────────────────────────────────────────┤
│ # │ Printer ID │ Name │ Loc │ Open │ Close │ Total │ Rate │ Amt │
│───┼────────────┼──────┼─────┼──────┼───────┼───────┼──────┼─────│
│ 1 │ HP001      │ ...  │ ... │ 10000│ 11500 │  1500 │ 1.75 │2625 │
├──────────────────────────────────────────────┤
│                             Sub Total: ₹7525  │
│                             CGST 9%:   ₹677.25│
│                             SGST 9%:   ₹677.25│
│                             ════════════════  │
│                             TOTAL:   ₹8879.50 │
├──────────────────────────────────────────────┤
│ Amount in Words: Eight Thousand Eight Hundred │
│                  Seventy Nine Rupees & 50 Paise│
├──────────────────────────────────────────────┤
│ Terms & Conditions       Authorised Signatory │
└──────────────────────────────────────────────┘
```

---

## ⚙️ Settings

Open via toolbar → Settings or **Ctrl+,**

| Setting | Description |
|---------|-------------|
| My Company Name | Appears in invoice header |
| Address / Phone / Email / GSTIN | Invoice header details |
| Logo Path | PNG/JPG logo for invoice |
| Invoice Prefix | e.g. `INV` → `INV/25-26/0001` |
| Financial Year Start | Month number (default: 4 = April) |
| Default CGST / SGST / IGST % | Pre-filled in billing dialog |
| Terms | Printed at invoice footer |

---

## 📊 Invoice Numbering

Format: `{PREFIX}/{FY}/{SEQUENCE}`

Example: `INV/25-26/0001`

- Financial Year determined by "FY Start Month" setting
- If FY starts April: April 2025 → FY 2025-26
- Sequence resets each financial year

---

## 🔮 Future Extensibility

The modular design makes it easy to add:

```python
# In billing_service.py calculate_bill():
# Add after subtotal calculation:
courier_charge = ...    # from a new charges table
discount = ...          # percentage or flat
penalty = ...           # late payment penalty
subtotal += courier_charge - discount + penalty
```

Suggested future enhancements:
- [ ] Courier / transportation charges per company
- [ ] Discount rules (% or flat)
- [ ] Late payment penalty
- [ ] Email invoice directly from app
- [ ] Multi-rate per company (B&W vs Colour)
- [ ] Recurring invoice scheduler
- [ ] Client portal (read-only web view)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│             UI Layer (PyQt5)            │
│  main_window → company_tab             │
│             → printer_tab              │
│             → counter_tab              │
│             → billing_tab              │
└────────────────┬────────────────────────┘
                 │  calls
┌────────────────▼────────────────────────┐
│           Services Layer                │
│  BillingService  PDFService  Excel      │
└────────────────┬────────────────────────┘
                 │  reads/writes
┌────────────────▼────────────────────────┐
│        Database Layer (SQLite)          │
│  DatabaseManager — single connection   │
│  manager, all SQL in one file          │
└─────────────────────────────────────────┘
```

**Key principles:**
- No SQL in UI files
- No UI imports in service files
- DatabaseManager is the only class that touches SQLite
- Services handle all business logic
- Helpers are pure functions with no side effects
