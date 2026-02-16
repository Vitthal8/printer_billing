"""
services/pdf_service.py
========================
Generates professional A4 invoice PDFs using ReportLab.

Key design decisions:
  • Uses Platypus (flowable document model) for proper pagination
  • Branded header with logo support
  • GST-compliant layout (CGST/SGST or IGST)
  • Amount in words on footer
  • QR-code slot reserved (can be enabled later)
"""

import os
from datetime import datetime

from reportlab.lib             import colors
from reportlab.lib.pagesizes   import A4
from reportlab.lib.units       import mm
from reportlab.lib.styles      import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums       import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus        import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.platypus        import Image as RLImage
from reportlab.pdfbase         import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from utils.helpers import month_year_label, format_currency, amount_in_words


# ── Brand Colours ────────────────────────────────────────────────────────────
PRIMARY     = colors.HexColor('#1a3c5e')   # dark navy
ACCENT      = colors.HexColor('#2e86c1')   # blue
LIGHT_BG    = colors.HexColor('#eaf3fb')   # light blue tint
GREY        = colors.HexColor('#666666')
LIGHT_GREY  = colors.HexColor('#f2f2f2')
WHITE       = colors.white
BLACK       = colors.black

W, H = A4    # 595.27 x 841.89 pts


class PDFService:
    """Generates invoice PDFs from invoice dicts produced by BillingService."""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    def generate_invoice(self, invoice: dict, output_path: str) -> str:
        """
        Build a PDF for `invoice` and save to `output_path`.
        Returns the final saved path.
        """
        settings = self.db.get_all_settings()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            topMargin=12*mm, bottomMargin=15*mm,
            leftMargin=15*mm, rightMargin=15*mm,
            title=f"Invoice {invoice['invoice_number']}",
            author=settings.get('my_company_name', 'PrintBill Pro'),
        )

        story = self._build_story(invoice, settings)
        doc.build(story,
                  onFirstPage=self._page_border,
                  onLaterPages=self._page_border)
        return output_path

    # ------------------------------------------------------------------ #
    #  Story builder                                                       #
    # ------------------------------------------------------------------ #

    def _build_story(self, inv: dict, s: dict) -> list:
        styles = self._make_styles()
        story  = []

        story += self._header_block(inv, s, styles)
        story.append(Spacer(1, 4*mm))
        story += self._bill_to_block(inv, styles)
        story.append(Spacer(1, 4*mm))
        story += self._items_table(inv, styles)
        story.append(Spacer(1, 4*mm))
        if inv.get('extras'):
            story += self._extras_block(inv, styles)
            story.append(Spacer(1, 4*mm))
        story += self._totals_block(inv, styles)
        story.append(Spacer(1, 3*mm))
        story += self._amount_in_words(inv, styles)
        story.append(Spacer(1, 4*mm))
        story += self._footer_block(inv, s, styles)

        return story

    # ── Header ────────────────────────────────────────────────────────── #

    def _header_block(self, inv, s, styles):
        logo_path  = s.get('logo_path', '')
        my_name    = s.get('my_company_name', 'Your Printing Services')
        my_addr    = s.get('my_company_address', '')
        my_phone   = s.get('my_company_phone', '')
        my_email   = s.get('my_company_email', '')
        my_gst     = s.get('my_company_gst', '')

        # Left column: logo or company name big
        if logo_path and os.path.exists(logo_path):
            try:
                logo = RLImage(logo_path, width=40*mm, height=15*mm,
                               kind='proportional')
                left_top = logo
            except Exception:
                left_top = Paragraph(my_name, styles['CompanyName'])
        else:
            left_top = Paragraph(my_name, styles['CompanyName'])

        addr_lines = [my_addr, my_phone, my_email]
        if my_gst:
            addr_lines.append(f"GSTIN: {my_gst}")
        addr_text = '<br/>'.join(filter(None, addr_lines))
        left_addr = Paragraph(addr_text, styles['SmallGrey'])

        # Right column: TAX INVOICE badge
        right_top  = Paragraph("TAX INVOICE", styles['InvoiceBadge'])
        inv_no     = Paragraph(
            f"<b>Invoice No:</b> {inv['invoice_number']}", styles['InvoiceDetail']
        )
        inv_date   = Paragraph(
            f"<b>Date:</b> {self._format_date(inv['invoice_date'])}", styles['InvoiceDetail']
        )
        period     = Paragraph(
            f"<b>Period:</b> {month_year_label(inv['month'], inv['year'])}",
            styles['InvoiceDetail']
        )

        # Table layout: [logo+addr | invoice badge+details]
        data = [[
            [left_top, Spacer(1, 2*mm), left_addr],
            [right_top, Spacer(1, 2*mm), inv_no, inv_date, period]
        ]]
        tbl = Table(data, colWidths=[95*mm, 80*mm])
        tbl.setStyle(TableStyle([
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
        ]))
        return [tbl]

    # ── Bill-To Block ─────────────────────────────────────────────────── #

    def _bill_to_block(self, inv, styles):
        label   = Paragraph("BILL TO", styles['SectionLabel'])
        name    = Paragraph(f"<b>{inv['company_name']}</b>", styles['ClientName'])
        address = Paragraph(inv.get('company_address', ''), styles['ClientAdd'])
        gst_txt = Paragraph(
            f"GSTIN: {inv.get('company_gst', 'N/A')}", styles['ClientAdd']
        )

        data = [[[label, Spacer(1, 1*mm), name, Spacer(1, 1*mm), address, gst_txt]]]
        tbl = Table(data, colWidths=[175*mm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), LIGHT_BG),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BOX',           (0, 0), (-1, -1), 0.5, ACCENT),
            ('ROUNDEDCORNERS', [3, 3, 3, 3]),
        ]))
        return [tbl]

    # ── Items Table ───────────────────────────────────────────────────── #

    def _items_table(self, inv, styles):
        header = [
            Paragraph('#',              styles['TH']),
            Paragraph('Printer ID',     styles['TH']),
            Paragraph('Printer Name',   styles['TH']),
            Paragraph('Location',       styles['TH']),
            Paragraph('Opening',        styles['TH']),
            Paragraph('Closing',        styles['TH']),
            Paragraph('Total Prints',   styles['TH']),
            Paragraph('Rate (₹)',       styles['TH']),
            Paragraph('Amount (₹)',     styles['TH']),
        ]
        rows = [header]

        for idx, item in enumerate(inv.get('items', []), start=1):
            row = [
                Paragraph(str(idx),                            styles['TD']),
                Paragraph(item.get('printer_serial', ''),      styles['TD']),
                Paragraph(item.get('printer_name', ''),        styles['TD']),
                Paragraph(item.get('location', ''),            styles['TD']),
                Paragraph(f"{item['opening_counter']:,}",      styles['TDR']),
                Paragraph(f"{item['closing_counter']:,}",      styles['TDR']),
                Paragraph(f"{item['total_prints']:,}",         styles['TDR']),
                Paragraph(f"{item['rate_per_print']:.2f}",     styles['TDR']),
                Paragraph(f"{item['amount']:,.2f}",            styles['TDR']),
            ]
            rows.append(row)

        col_w = [8*mm, 28*mm, 32*mm, 25*mm, 18*mm, 18*mm, 18*mm, 14*mm, 22*mm]
        tbl = Table(rows, colWidths=col_w, repeatRows=1)

        ts = TableStyle([
            # Header
            ('BACKGROUND',    (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR',     (0, 0), (-1, 0), WHITE),
            ('FONTSIZE',      (0, 0), (-1, 0), 8),
            ('TOPPADDING',    (0, 0), (-1, 0), 5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            # Body alternating rows
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
            ('FONTSIZE',      (0, 1), (-1, -1), 8),
            ('TOPPADDING',    (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            # Grid
            ('GRID',          (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
            ('BOX',           (0, 0), (-1, -1), 0.8, PRIMARY),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ])
        tbl.setStyle(ts)
        return [tbl]

    # ── Totals Block ──────────────────────────────────────────────────── #

    def _extras_block(self, inv, styles):
        """Render extra charges and discounts table."""
        # Section header row
        rows = [[
            Paragraph('Extra Charges & Discounts', styles['SectionLabel']),
            Paragraph('', styles['TH']),
            Paragraph('', styles['TH']),
        ]]
        header = [
            Paragraph('#',           styles['TH']),
            Paragraph('Description', styles['TH']),
            Paragraph('Amount (Rs)', styles['TH']),
        ]
        rows.append(header)

        charge_rows   = []
        discount_rows = []

        for ex in inv.get('extras', []):
            is_discount = ex['extra_type'] == 'discount'
            taxable_txt = ' *' if ex.get('taxable', True) else ''
            desc = ex['description'] + taxable_txt
            amt  = float(ex['amount'])
            if is_discount:
                discount_rows.append((desc, amt))
            else:
                charge_rows.append((desc, amt))

        counter = 1
        for desc, amt in charge_rows:
            rows.append([
                Paragraph(str(counter), styles['TD']),
                Paragraph(desc,         styles['TD']),
                Paragraph(f'{amt:,.2f}', styles['TDR']),
            ])
            counter += 1

        for desc, amt in discount_rows:
            rows.append([
                Paragraph(str(counter), styles['TD']),
                Paragraph(f'(-) {desc}', styles['TD']),
                Paragraph(f'({amt:,.2f})', styles['TDR']),
            ])
            counter += 1

        col_w = [10*mm, 140*mm, 30*mm]
        tbl = Table(rows, colWidths=col_w)
        ts = TableStyle([
            # Section label row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f4fc')),
            ('SPAN',       (0, 0), (-1, 0)),
            ('TOPPADDING', (0, 0), (-1, 0), 4),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            # Header row
            ('BACKGROUND', (0, 1), (-1, 1), ACCENT),
            ('TEXTCOLOR',  (0, 1), (-1, 1), WHITE),
            ('FONTSIZE',   (0, 1), (-1, 1), 8),
            # Body
            ('FONTSIZE',   (0, 2), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 2), (-1, -1), [WHITE, colors.HexColor('#f9f9f9')]),
            ('TOPPADDING',    (0, 2), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 2), (-1, -1), 4),
            ('GRID',          (0, 1), (-1, -1), 0.3, colors.HexColor('#cccccc')),
            ('BOX',           (0, 0), (-1, -1), 0.8, PRIMARY),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ])
        tbl.setStyle(ts)

        note = Paragraph(
            "* Amount included in GST calculation",
            styles['SmallFootnote']
        )
        return [tbl, Spacer(1, 1*mm), note]

    def _totals_block(self, inv, styles):
        rows = []

        def add_row(label, value, bold=False, color=None):
            sty_l = styles['TotalsBold']   if bold else styles['TotalsNormal']
            sty_r = styles['TotalsBoldRight'] if bold else styles['TotalsRight']
            if color:
                sty_l = ParagraphStyle('tmp_l', parent=sty_l, textColor=color)
                sty_r = ParagraphStyle('tmp_r', parent=sty_r, textColor=color)
            rows.append([
                Paragraph('', styles['TotalsNormal']),
                Paragraph(label, sty_l),
                Paragraph(value, sty_r),
            ])

        add_row("Print Charges:", format_currency(inv['subtotal']))

        # Extra charges
        for ex in inv.get('extras', []):
            if ex['extra_type'] == 'charge':
                taxable_mark = ' *' if ex.get('taxable', True) else ''
                add_row(f"  + {ex['description']}{taxable_mark}:",
                        format_currency(ex['amount']))

        # Discounts
        for ex in inv.get('extras', []):
            if ex['extra_type'] == 'discount':
                taxable_mark = ' *' if ex.get('taxable', True) else ''
                add_row(f"  - {ex['description']}{taxable_mark}:",
                        format_currency(ex['amount']),
                        color=colors.HexColor('#c0392b'))

        # Tax rows
        if inv.get('cgst_rate', 0):
            add_row(f"CGST @ {inv['cgst_rate']:.1f}% *:",
                    format_currency(inv['cgst_amount']))
        if inv.get('sgst_rate', 0):
            add_row(f"SGST @ {inv['sgst_rate']:.1f}% *:",
                    format_currency(inv['sgst_amount']))
        if inv.get('igst_rate', 0):
            add_row(f"IGST @ {inv['igst_rate']:.1f}% *:",
                    format_currency(inv['igst_amount']))

        rows.append([
            Paragraph('', styles['TotalsNormal']),
            HRFlowable(width='100%', thickness=1, color=ACCENT),
            HRFlowable(width='100%', thickness=1, color=ACCENT),
        ])

        add_row("TOTAL AMOUNT:", format_currency(inv['total_amount']), bold=True)

        tbl = Table(rows, colWidths=[97*mm, 52*mm, 31*mm])
        tbl.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('BACKGROUND',    (1, -1), (-1, -1), LIGHT_BG),
        ]))
        return [tbl]

    # ── Amount in Words ───────────────────────────────────────────────── #

    def _amount_in_words(self, inv, styles):
        words = amount_in_words(inv['total_amount'])
        data  = [[Paragraph(f"<b>Amount in Words:</b> {words}", styles['AmountWords'])]]
        tbl   = Table(data, colWidths=[175*mm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, -1), LIGHT_BG),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING',  (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('BOX',         (0, 0), (-1, -1), 0.5, ACCENT),
        ]))
        return [tbl]

    # ── Footer ────────────────────────────────────────────────────────── #

    def _footer_block(self, inv, s, styles):
        terms = s.get('terms', 'Payment due within 30 days of invoice date.')
        notes = inv.get('notes', '').strip()
        items = []

        if notes:
            items.append(Paragraph(f"<b>Notes:</b> {notes}", styles['SmallGrey']))
            items.append(Spacer(1, 2*mm))

        items.append(HRFlowable(width='100%', thickness=0.5, color=GREY))
        items.append(Spacer(1, 2*mm))

        # Two-column footer: terms left, signature right
        sig_text = (
            f"<br/><br/>________________________<br/>"
            f"<b>{s.get('my_company_name','')}</b><br/>"
            "<font size='8'>Authorised Signatory</font>"
        )
        data = [[
            Paragraph(f"<b>Terms & Conditions:</b><br/>{terms}", styles['SmallGrey']),
            Paragraph(sig_text, styles['Signature']),
        ]]
        tbl = Table(data, colWidths=[115*mm, 55*mm])
        tbl.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING',   (0, 0), (0, 0),   0),
            ('RIGHTPADDING',  (-1, 0), (-1, -1), 0),
        ]))
        items.append(tbl)
        return items

    # ── Page border callback ──────────────────────────────────────────── #

    @staticmethod
    def _page_border(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(PRIMARY)
        canvas.setLineWidth(2)
        canvas.roundRect(8*mm, 8*mm, W - 16*mm, H - 16*mm, 3*mm)
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(GREY)
        canvas.drawCentredString(W / 2, 6*mm,
            f"Generated by PrintBill Pro  |  Page {doc.page}")
        canvas.restoreState()

    # ── Style definitions ─────────────────────────────────────────────── #

    @staticmethod
    def _make_styles() -> dict:
        base = getSampleStyleSheet()

        def P(name, parent='Normal', **kw) -> ParagraphStyle:
            return ParagraphStyle(name, parent=base[parent], **kw)

        return {
            'CompanyName': P('CompanyName', fontSize=16, textColor=WHITE,
                              fontName='Helvetica-Bold', spaceAfter=0),
            'SmallGrey':   P('SmallGrey',  fontSize=8,  textColor=WHITE,
                              leading=11, spaceAfter=0),
            'InvoiceBadge':P('InvoiceBadge', fontSize=14, textColor=WHITE,
                              fontName='Helvetica-Bold', alignment=TA_RIGHT),
            'InvoiceDetail':P('InvoiceDetail', fontSize=9, textColor=WHITE,
                               alignment=TA_RIGHT, spaceAfter=0),
            'SectionLabel':P('SectionLabel', fontSize=7, textColor=ACCENT,
                              fontName='Helvetica-Bold', spaceAfter=1),
            'ClientName':  P('ClientName',  fontSize=11, textColor=PRIMARY,
                              fontName='Helvetica-Bold'),
            'ClientAdd': P('ClientAdd',  fontSize=8,  textColor=PRIMARY,
                            leading=11, spaceAfter=0),
            'TH':          P('TH', fontSize=8, textColor=WHITE,
                              fontName='Helvetica-Bold', alignment=TA_CENTER,
                              spaceAfter=0),
            'TD':          P('TD', fontSize=8, textColor=BLACK,
                              alignment=TA_LEFT, spaceAfter=0),
            'TDR':         P('TDR', fontSize=8, textColor=BLACK,
                              alignment=TA_RIGHT, spaceAfter=0),
            'TotalsNormal':P('TotalsNormal', fontSize=9, textColor=BLACK,
                              alignment=TA_RIGHT, spaceAfter=0),
            'TotalsRight': P('TotalsRight',  fontSize=9, textColor=BLACK,
                              alignment=TA_RIGHT, spaceAfter=0),
            'TotalsBold':  P('TotalsBold',   fontSize=10, textColor=PRIMARY,
                              fontName='Helvetica-Bold', alignment=TA_RIGHT, spaceAfter=0),
            'TotalsBoldRight': P('TotalsBoldRight', fontSize=10, textColor=PRIMARY,
                                  fontName='Helvetica-Bold', alignment=TA_RIGHT, spaceAfter=0),
            'AmountWords': P('AmountWords', fontSize=9, textColor=PRIMARY,
                              spaceAfter=0),
            'Signature':   P('Signature', fontSize=9, textColor=BLACK,
                              alignment=TA_RIGHT, spaceAfter=0),
            'SmallFootnote': P('SmallFootnote', fontSize=7, textColor=GREY,
                                fontName='Helvetica-Oblique', spaceAfter=0),
        }

    # ── Helpers ───────────────────────────────────────────────────────── #

    @staticmethod
    def _format_date(date_str: str) -> str:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d %b %Y')
        except Exception:
            return date_str
