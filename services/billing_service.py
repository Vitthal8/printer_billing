"""
services/billing_service.py
============================
Pure business logic for bill generation.
Supports: printer charges, extra charges (service, parts), discounts.

GST calculation order:
  1. Print subtotal  = sum(prints x rate)
  2. Taxable base    = print_subtotal + taxable_charges - taxable_discounts
  3. Tax             = taxable_base x (CGST% + SGST%)  or  x IGST%
  4. Grand total     = print_subtotal + ALL extras - ALL discounts + tax
"""

from datetime import datetime
from database.connection import DatabaseManager
from utils.helpers import safe_float


class BillingService:
    GST_NONE      = 'none'
    GST_CGST_SGST = 'cgst_sgst'
    GST_IGST      = 'igst'

    EXTRA_CHARGE   = 'charge'
    EXTRA_DISCOUNT = 'discount'

    def __init__(self, db: DatabaseManager):
        self.db = db

    def calculate_bill(self, company_id: int, month: int, year: int,
                       gst_type: str = GST_CGST_SGST,
                       custom_cgst: float | None = None,
                       custom_sgst: float | None = None,
                       custom_igst: float | None = None,
                       extras: list | None = None,
                       notes: str = '') -> dict:
        """
        Calculate a billing preview.

        extras format:
          [{'description': 'Service Charge', 'extra_type': 'charge',
            'amount': 500.0, 'taxable': True}, ...]

        Returns full invoice dict with 'items' and 'extras'. Does NOT save.
        """
        company = self.db.get_company(company_id)
        if not company:
            raise ValueError(f"Company #{company_id} not found.")

        if self.db.invoice_exists(company_id, month, year):
            raise ValueError(
                f"Invoice already generated for {company['name']} "
                f"for {month}/{year}. Delete it first to regenerate."
            )

        readings = self.db.get_counter_readings_for_company_month(
            company_id, month, year
        )
        if not readings:
            raise ValueError(
                f"No counter readings found for {company['name']} "
                f"for {month}/{year}. Please enter counter data first."
            )

        # Build printer line items
        items        = []
        total_prints = 0
        subtotal     = 0.0

        for r in readings:
            prints = int(r['total_prints'])
            rate   = safe_float(company['rate_per_print'])
            amount = round(prints * rate, 2)
            items.append({
                'printer_id':      r['printer_id'],
                'printer_name':    r['printer_name'] or '',
                'printer_serial':  r['printer_serial'],
                'location':        r.get('location') or '',
                'opening_counter': r['opening_counter'],
                'closing_counter': r['closing_counter'],
                'total_prints':    prints,
                'rate_per_print':  rate,
                'amount':          amount,
            })
            total_prints += prints
            subtotal     += amount

        subtotal = round(subtotal, 2)

        # Process extras
        clean_extras   = []
        extras_total   = 0.0
        discount_total = 0.0
        taxable_add    = 0.0
        taxable_sub    = 0.0

        for idx, ex in enumerate(extras or []):
            amt = round(safe_float(ex.get('amount', 0)), 2)
            if amt <= 0:
                continue
            etype   = ex.get('extra_type', self.EXTRA_CHARGE)
            taxable = bool(ex.get('taxable', True))
            clean_extras.append({
                'description': str(ex.get('description', '')).strip(),
                'extra_type':  etype,
                'amount':      amt,
                'taxable':     taxable,
                'sort_order':  idx,
            })
            if etype == self.EXTRA_CHARGE:
                extras_total += amt
                if taxable: taxable_add += amt
            else:
                discount_total += amt
                if taxable: taxable_sub += amt

        extras_total   = round(extras_total,   2)
        discount_total = round(discount_total, 2)

        # GST rates
        cgst_rate = safe_float(custom_cgst if custom_cgst is not None
                               else self.db.get_setting('default_cgst_rate', '9'))
        sgst_rate = safe_float(custom_sgst if custom_sgst is not None
                               else self.db.get_setting('default_sgst_rate', '9'))
        igst_rate = safe_float(custom_igst if custom_igst is not None
                               else self.db.get_setting('default_igst_rate', '18'))

        # Taxable base includes only taxable extras/discounts
        taxable_base = max(0.0, round(subtotal + taxable_add - taxable_sub, 2))

        cgst_amount = sgst_amount = igst_amount = 0.0
        if gst_type == self.GST_CGST_SGST:
            cgst_amount = round(taxable_base * cgst_rate / 100, 2)
            sgst_amount = round(taxable_base * sgst_rate / 100, 2)
        elif gst_type == self.GST_IGST:
            igst_amount = round(taxable_base * igst_rate / 100, 2)

        total_amount = round(
            subtotal + extras_total - discount_total
            + cgst_amount + sgst_amount + igst_amount, 2
        )

        return {
            'invoice_number':  self.db.get_next_invoice_number(),
            'company_id':      company_id,
            'company_name':    company['name'],
            'company_address': company.get('address', ''),
            'company_gst':     company.get('gst_number', ''),
            'month':           month,
            'year':            year,
            'invoice_date':    datetime.now().strftime('%Y-%m-%d'),
            'total_prints':    total_prints,
            'rate_per_print':  safe_float(company['rate_per_print']),
            'subtotal':        subtotal,
            'extras_total':    extras_total,
            'discount_total':  discount_total,
            'gst_type':        gst_type,
            'cgst_rate':       cgst_rate  if gst_type == self.GST_CGST_SGST else 0.0,
            'sgst_rate':       sgst_rate  if gst_type == self.GST_CGST_SGST else 0.0,
            'igst_rate':       igst_rate  if gst_type == self.GST_IGST       else 0.0,
            'cgst_amount':     cgst_amount,
            'sgst_amount':     sgst_amount,
            'igst_amount':     igst_amount,
            'total_amount':    total_amount,
            'notes':           notes,
            'items':           items,
            'extras':          clean_extras,
        }

    def finalise_bill(self, preview: dict) -> int:
        skip = {'items', 'extras', 'company_name', 'company_address',
                'company_gst', 'gst_type'}
        invoice_data = {k: v for k, v in preview.items() if k not in skip}
        return self.db.create_invoice(invoice_data,
                                      preview['items'],
                                      preview.get('extras', []))

    def regenerate_bill(self, invoice_id: int,
                        gst_type: str = GST_CGST_SGST,
                        notes: str = '') -> int:
        inv = self.db.get_invoice(invoice_id)
        if not inv:
            raise ValueError(f"Invoice #{invoice_id} not found.")
        existing_extras = inv.get('extras', [])
        self.db.delete_invoice(invoice_id)
        preview = self.calculate_bill(
            inv['company_id'], inv['month'], inv['year'],
            gst_type=gst_type, notes=notes, extras=existing_extras
        )
        return self.finalise_bill(preview)

    def get_billing_summary(self, year: int) -> list[dict]:
        from utils.helpers import month_name
        invoices = self.db.get_all_invoices(year=year)
        summary = {}
        for inv in invoices:
            m = inv['month']
            if m not in summary:
                summary[m] = {'month': m, 'month_name': month_name(m),
                               'total_invoices': 0, 'total_amount': 0.0}
            summary[m]['total_invoices'] += 1
            summary[m]['total_amount']   += inv['total_amount']
        return [summary[m] for m in sorted(summary)]
