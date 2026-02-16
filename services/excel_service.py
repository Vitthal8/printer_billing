"""
services/excel_service.py
==========================
Exports invoice and counter-reading data to Excel using openpyxl.
Three export modes:
  1. Single invoice → one sheet with full breakdown
  2. All invoices for a period → summary sheet + per-company sheets
  3. Counter readings → raw data sheet for audit
"""

import os
from datetime import datetime

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side,
    numbers as xl_numbers
)
from openpyxl.utils import get_column_letter

from utils.helpers import month_year_label, format_currency


# ── Style constants ──────────────────────────────────────────────────────────
HDR_FILL  = PatternFill("solid", fgColor="1A3C5E")  # dark navy
SUB_FILL  = PatternFill("solid", fgColor="2E86C1")  # blue
ALT_FILL  = PatternFill("solid", fgColor="EAF3FB")  # light blue
HDR_FONT  = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
SUB_FONT  = Font(name="Calibri", bold=True, color="FFFFFF", size=9)
BODY_FONT = Font(name="Calibri", size=9)
TITLE_FONT= Font(name="Calibri", bold=True, size=12, color="1A3C5E")

THIN  = Side(style="thin",   color="CCCCCC")
MED   = Side(style="medium", color="1A3C5E")
BORDER_ALL   = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BORDER_THICK = Border(left=MED,  right=MED,  top=MED,  bottom=MED)

NUM_FMT  = '#,##0'
CURR_FMT = '₹#,##0.00'


def _col_width(ws, col_letter, width):
    ws.column_dimensions[col_letter].width = width


def _hdr_row(ws, row, values, fill=HDR_FILL, font=HDR_FONT):
    for col, val in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BORDER_ALL


def _body_row(ws, row, values, alt=False):
    fill = ALT_FILL if alt else PatternFill()
    for col, val in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.font = BODY_FONT
        cell.fill = fill
        cell.border = BORDER_ALL
        cell.alignment = Alignment(vertical='center')


class ExcelService:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------ #
    #  Export single invoice                                               #
    # ------------------------------------------------------------------ #

    def export_invoice(self, invoice_id: int, output_path: str) -> str:
        inv = self.db.get_invoice(invoice_id)
        if not inv:
            raise ValueError(f"Invoice #{invoice_id} not found.")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Invoice"
        ws.sheet_view.showGridLines = False

        self._write_invoice_sheet(ws, inv)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        wb.save(output_path)
        return output_path

    def _write_invoice_sheet(self, ws, inv):
        s = self.db.get_all_settings()

        # ── Title area ────────────────────────────────────────────────
        ws.merge_cells("A1:I1")
        t = ws["A1"]
        t.value = s.get("my_company_name", "Your Printing Services")
        t.font  = Font(name="Calibri", bold=True, size=14, color="1A3C5E")
        t.alignment = Alignment(horizontal="center")

        ws.merge_cells("A2:I2")
        t2 = ws["A2"]
        t2.value = "TAX INVOICE"
        t2.font  = Font(name="Calibri", bold=True, size=11, color="2E86C1")
        t2.alignment = Alignment(horizontal="center")

        ws.merge_cells("A3:I3")  # spacer

        # Invoice meta
        meta = [
            ("Invoice No:",  inv["invoice_number"]),
            ("Date:",        inv["invoice_date"]),
            ("Period:",      month_year_label(inv["month"], inv["year"])),
            ("Bill To:",     inv["company_name"]),
            ("Address:",     inv.get("company_address", "")),
            ("GSTIN (Client):", inv.get("company_gst", "N/A")),
            ("GSTIN (Us):",  s.get("my_company_gst", "")),
        ]
        for r, (lbl, val) in enumerate(meta, start=4):
            ws.cell(row=r, column=1, value=lbl).font = Font(name="Calibri", bold=True, size=9)
            ws.cell(row=r, column=2, value=val).font = BODY_FONT
            ws.merge_cells(f"B{r}:I{r}")

        row = 4 + len(meta) + 1

        # ── Item header ───────────────────────────────────────────────
        headers = ["#", "Printer ID", "Printer Name", "Location",
                   "Opening", "Closing", "Total Prints", "Rate (₹)", "Amount (₹)"]
        _hdr_row(ws, row, headers)
        row += 1

        for idx, item in enumerate(inv.get("items", []), start=1):
            vals = [
                idx,
                item.get("printer_serial", ""),
                item.get("printer_name", ""),
                item.get("location", ""),
                item["opening_counter"],
                item["closing_counter"],
                item["total_prints"],
                item["rate_per_print"],
                item["amount"],
            ]
            _body_row(ws, row, vals, alt=(idx % 2 == 0))
            # Number formats
            for col in [5, 6, 7]:
                ws.cell(row=row, column=col).number_format = NUM_FMT
            for col in [8, 9]:
                ws.cell(row=row, column=col).number_format = CURR_FMT
            row += 1

        # ── Totals ────────────────────────────────────────────────────
        row += 1
        def total_row(label, value, bold=False):
            nonlocal row
            ws.merge_cells(f"A{row}:G{row}")
            c1 = ws.cell(row=row, column=8, value=label)
            c2 = ws.cell(row=row, column=9, value=value)
            if bold:
                c1.font = Font(name="Calibri", bold=True, size=10, color="1A3C5E")
                c2.font = Font(name="Calibri", bold=True, size=10, color="1A3C5E")
                c1.fill = ALT_FILL
                c2.fill = ALT_FILL
            else:
                c1.font = BODY_FONT
                c2.font = BODY_FONT
            c1.alignment = Alignment(horizontal="right")
            c2.alignment = Alignment(horizontal="right")
            c2.number_format = CURR_FMT
            c1.border = BORDER_ALL
            c2.border = BORDER_ALL
            row += 1

        total_row("Sub Total:", inv["subtotal"])
        if inv.get("cgst_rate", 0):
            total_row(f"CGST @ {inv['cgst_rate']:.1f}%:", inv["cgst_amount"])
        if inv.get("sgst_rate", 0):
            total_row(f"SGST @ {inv['sgst_rate']:.1f}%:", inv["sgst_amount"])
        if inv.get("igst_rate", 0):
            total_row(f"IGST @ {inv['igst_rate']:.1f}%:", inv["igst_amount"])
        total_row("TOTAL AMOUNT:", inv["total_amount"], bold=True)

        # ── Amount in words ───────────────────────────────────────────
        row += 1
        ws.merge_cells(f"A{row}:I{row}")
        from utils.helpers import amount_in_words
        aw = ws[f"A{row}"]
        aw.value = f"Amount in Words: {amount_in_words(inv['total_amount'])}"
        aw.font  = Font(name="Calibri", italic=True, size=9, color="1A3C5E")
        aw.fill  = ALT_FILL

        # ── Column widths ─────────────────────────────────────────────
        widths = [4, 14, 18, 14, 10, 10, 12, 12, 14]
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # ------------------------------------------------------------------ #
    #  Export all invoices summary                                         #
    # ------------------------------------------------------------------ #

    def export_invoices_summary(self, output_path: str,
                                 company_id=None, year=None) -> str:
        invoices = self.db.get_all_invoices(company_id=company_id, year=year)
        if not invoices:
            raise ValueError("No invoices found for the selected filters.")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Summary"
        ws.sheet_view.showGridLines = False

        # Title
        ws.merge_cells("A1:J1")
        ws["A1"].value = "Invoice Summary Report"
        ws["A1"].font  = TITLE_FONT
        ws["A1"].alignment = Alignment(horizontal="center")

        ws.merge_cells("A2:J2")
        ws["A2"].value = f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}"
        ws["A2"].font  = Font(name="Calibri", size=9, color="666666")
        ws["A2"].alignment = Alignment(horizontal="center")

        headers = ["#", "Invoice No", "Company", "Month", "Year",
                   "Total Prints", "Sub Total (₹)", "Tax (₹)", "Total Amount (₹)", "Status"]
        _hdr_row(ws, 4, headers)

        total_amount = 0
        for idx, inv in enumerate(invoices, start=1):
            tax = inv["cgst_amount"] + inv["sgst_amount"] + inv["igst_amount"]
            vals = [
                idx,
                inv["invoice_number"],
                inv["company_name"],
                month_year_label(inv["month"], inv["year"]),
                inv["year"],
                inv["total_prints"],
                inv["subtotal"],
                tax,
                inv["total_amount"],
                inv["status"].title(),
            ]
            _body_row(ws, 4 + idx, vals, alt=(idx % 2 == 0))
            for col in [6]:
                ws.cell(row=4 + idx, column=col).number_format = NUM_FMT
            for col in [7, 8, 9]:
                ws.cell(row=4 + idx, column=col).number_format = CURR_FMT
            total_amount += inv["total_amount"]

        # Grand total row
        gr = 5 + len(invoices)
        ws.cell(row=gr, column=9, value=total_amount).number_format = CURR_FMT
        ws.cell(row=gr, column=9).font = Font(name="Calibri", bold=True, size=10)
        ws.merge_cells(f"A{gr}:H{gr}")
        ws.cell(row=gr, column=1, value="GRAND TOTAL").font = Font(
            name="Calibri", bold=True, size=10, color="1A3C5E")
        ws.cell(row=gr, column=1).alignment = Alignment(horizontal="right")

        # Column widths
        for col, w in zip("ABCDEFGHIJ", [4, 16, 22, 14, 8, 12, 16, 14, 18, 12]):
            ws.column_dimensions[col].width = w

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        wb.save(output_path)
        return output_path

    # ------------------------------------------------------------------ #
    #  Export counter readings                                             #
    # ------------------------------------------------------------------ #

    def export_counter_readings(self, output_path: str,
                                 company_id=None, month=None, year=None) -> str:
        readings = self.db.get_all_counter_readings(
            company_id=company_id, month=month, year=year
        )
        if not readings:
            raise ValueError("No counter readings for the selected filters.")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Counter Readings"
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:H1")
        ws["A1"].value = "Counter Readings Export"
        ws["A1"].font  = TITLE_FONT
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = ["#", "Company", "Printer ID", "Printer Name",
                   "Month", "Year", "Opening", "Closing", "Total Prints"]
        _hdr_row(ws, 3, headers)

        for idx, r in enumerate(readings, start=1):
            vals = [
                idx,
                r["company_name"],
                r["printer_serial"],
                r.get("printer_name", ""),
                month_year_label(r["month"], r["year"]),
                r["year"],
                r["opening_counter"],
                r["closing_counter"],
                r["total_prints"],
            ]
            _body_row(ws, 3 + idx, vals, alt=(idx % 2 == 0))
            for col in [7, 8, 9]:
                ws.cell(row=3 + idx, column=col).number_format = NUM_FMT

        for col, w in zip("ABCDEFGHI", [4, 22, 14, 18, 12, 8, 12, 12, 12]):
            ws.column_dimensions[col].width = w

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        wb.save(output_path)
        return output_path
