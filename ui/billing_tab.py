"""
ui/billing_tab.py
==================
Invoice generation + history tab.

Two sub-panels:
  ┌─────────────────────────────────────┐
  │  Generate Bill (left panel)         │
  │  • Select company / month / year    │
  │  • Pick GST type + rates            │
  │  • Preview calculated amounts       │
  │  • Generate → creates PDF + DB row  │
  └─────────────────────────────────────┘
  ┌─────────────────────────────────────┐
  │  Invoice History (right panel)      │
  │  • Filterable table                 │
  │  • Download PDF / Export Excel      │
  │  • Delete invoice                   │
  └─────────────────────────────────────┘
"""

import os
import subprocess
import platform

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView, QGroupBox, QFormLayout,
    QDoubleSpinBox, QSplitter, QTextEdit, QFrame, QButtonGroup,
    QRadioButton, QFileDialog, QLineEdit, QCheckBox,
    QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui  import QColor, QFont

from services.billing_service import BillingService
from services.pdf_service     import PDFService
from services.excel_service   import ExcelService
from utils.helpers import (
    MONTHS, current_month, current_year, year_range,
    month_year_label, format_currency
)


class BillingTab(QWidget):

    def __init__(self, db):
        super().__init__()
        self.db       = db
        self.billing  = BillingService(db)
        self.pdf_svc  = PDFService(db)
        self.excel_svc = ExcelService(db)
        self._preview_data = None   # holds last calculated bill preview

        self._build_ui()
        self._populate_selectors()
        self.refresh_history()

    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setSpacing(12)
        main.setContentsMargins(16, 16, 16, 16)

        # ── Left: Generate bill ───────────────────────────────────────
        # Left panel wrapped in a scroll area so nothing gets squished
        left_inner = QWidget()
        left_inner.setMinimumWidth(420)
        lv = QVBoxLayout(left_inner)
        left = QScrollArea()
        left.setWidget(left_inner)
        left.setWidgetResizable(True)
        left.setMinimumWidth(440)
        left.setMaximumWidth(520)
        left.setFrameShape(QFrame.NoFrame)
        left.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lv.setSpacing(10)

        lbl = QLabel("🧾  Generate Bill")
        lbl.setStyleSheet("font-size:16px; font-weight:700; color:#1a3c5e;")
        lv.addWidget(lbl)

        # Period selection
        period_grp = QGroupBox("Billing Period")
        pfl = QFormLayout(period_grp)
        pfl.setSpacing(8)
        pfl.setLabelAlignment(Qt.AlignRight)

        self.cbo_company = QComboBox()
        self.cbo_month   = QComboBox()
        self.cbo_year    = QComboBox()
        for i, m in enumerate(MONTHS, 1):
            self.cbo_month.addItem(m, i)
        self.cbo_month.setCurrentIndex(current_month() - 1)
        for y in reversed(year_range()):
            self.cbo_year.addItem(str(y), y)

        pfl.addRow("Company:",  self.cbo_company)
        pfl.addRow("Month:",    self.cbo_month)
        pfl.addRow("Year:",     self.cbo_year)
        lv.addWidget(period_grp)

        # GST settings
        gst_grp = QGroupBox("GST Settings")
        gv = QVBoxLayout(gst_grp)

        self.rb_cgst = QRadioButton("CGST + SGST (Intra-State)")
        self.rb_igst = QRadioButton("IGST (Inter-State)")
        self.rb_none = QRadioButton("No GST")
        self.rb_cgst.setChecked(True)
        for rb in [self.rb_cgst, self.rb_igst, self.rb_none]:
            gv.addWidget(rb)
            rb.toggled.connect(self._on_gst_toggle)

        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("CGST %:"))
        self.spin_cgst = QDoubleSpinBox()
        self.spin_cgst.setRange(0, 28); self.spin_cgst.setValue(9); self.spin_cgst.setDecimals(2)
        rate_row.addWidget(self.spin_cgst)
        rate_row.addWidget(QLabel("SGST %:"))
        self.spin_sgst = QDoubleSpinBox()
        self.spin_sgst.setRange(0, 28); self.spin_sgst.setValue(9); self.spin_sgst.setDecimals(2)
        rate_row.addWidget(self.spin_sgst)
        gv.addLayout(rate_row)

        igst_row = QHBoxLayout()
        igst_row.addWidget(QLabel("IGST %:"))
        self.spin_igst = QDoubleSpinBox()
        self.spin_igst.setRange(0, 28); self.spin_igst.setValue(18); self.spin_igst.setDecimals(2)
        igst_row.addWidget(self.spin_igst)
        igst_row.addStretch()
        gv.addLayout(igst_row)
        lv.addWidget(gst_grp)

        # Extra Charges / Discounts — stable QTableWidget approach
        extras_grp = QGroupBox("Extra Charges & Discounts")
        extras_grp.setStyleSheet("QGroupBox { font-weight:600; }")
        ev = QVBoxLayout(extras_grp)
        ev.setSpacing(6)

        self.extras_table = QTableWidget(0, 4)
        self.extras_table.setHorizontalHeaderLabels(
            ["Description", "Type", "Amount (Rs)", "GST?"]
        )
        self.extras_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.extras_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.extras_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.extras_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.extras_table.setColumnWidth(1, 110)
        self.extras_table.setColumnWidth(2, 130)
        self.extras_table.setColumnWidth(3,  58)
        self.extras_table.verticalHeader().setVisible(False)
        self.extras_table.setAlternatingRowColors(True)
        self.extras_table.setMinimumHeight(180)
        self.extras_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.extras_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.extras_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.extras_table.setStyleSheet("""
            QTableWidget { font-size:13px; }
            QTableWidget::item { padding: 3px 6px; }
            QHeaderView::section { font-size:12px; padding:6px 8px; }
            QLineEdit  { font-size:13px; padding:3px 6px; border:none; background:transparent; }
            QComboBox  { font-size:13px; font-weight:600; }
            QDoubleSpinBox { font-size:13px; border:none; background:transparent; }
        """)
        ev.addWidget(self.extras_table)

        ebtn_row = QHBoxLayout()
        btn_add_extra = QPushButton("➕  Add Row")
        btn_add_extra.setObjectName("btn_secondary")
        btn_add_extra.setFixedHeight(28)
        btn_add_extra.clicked.connect(self._add_extra_row)
        ebtn_row.addWidget(btn_add_extra)

        btn_del_extra = QPushButton("✕  Remove Row")
        btn_del_extra.setObjectName("btn_danger")
        btn_del_extra.setFixedHeight(28)
        btn_del_extra.clicked.connect(self._remove_extra_row)
        ebtn_row.addWidget(btn_del_extra)
        ebtn_row.addStretch()
        ev.addLayout(ebtn_row)
        lv.addWidget(extras_grp)

        # Preview button
        btn_preview = QPushButton("🔍  Calculate Preview")
        btn_preview.setObjectName("btn_warning")
        btn_preview.clicked.connect(self._calculate_preview)
        lv.addWidget(btn_preview)

        # Preview box
        preview_grp = QGroupBox("Bill Preview")
        pv = QVBoxLayout(preview_grp)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(110)
        self.preview_text.setMaximumHeight(145)
        self.preview_text.setStyleSheet(
            "background:#f0f4f8; border:1px solid #cdd5dc; "
            "font-family:'Courier New', monospace; font-size:12px;"
        )
        pv.addWidget(self.preview_text)
        lv.addWidget(preview_grp)

        # Generate button
        self.btn_generate = QPushButton("⚡  Generate Invoice & PDF")
        self.btn_generate.setObjectName("btn_success")
        self.btn_generate.setMinimumHeight(40)
        self.btn_generate.clicked.connect(self._generate_invoice)
        self.btn_generate.setEnabled(False)
        lv.addWidget(self.btn_generate)

        lv.addSpacing(8)
        main.addWidget(left)

        # ── Separator ─────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #cdd5dc;")
        main.addWidget(sep)

        # ── Right: Invoice history ────────────────────────────────────
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setSpacing(8)

        hist_lbl = QLabel("📋  Invoice History")
        hist_lbl.setStyleSheet("font-size:16px; font-weight:700; color:#1a3c5e;")
        rv.addWidget(hist_lbl)

        # Filter bar
        fbar = QHBoxLayout()
        fbar.addWidget(QLabel("Company:"))
        self.hist_cbo_company = QComboBox()
        self.hist_cbo_company.setFixedWidth(160)
        self.hist_cbo_company.currentIndexChanged.connect(self.refresh_history)
        fbar.addWidget(self.hist_cbo_company)

        fbar.addWidget(QLabel("Year:"))
        self.hist_cbo_year = QComboBox()
        self.hist_cbo_year.setFixedWidth(80)
        self.hist_cbo_year.addItem("All", None)
        for y in reversed(year_range()):
            self.hist_cbo_year.addItem(str(y), y)
        self.hist_cbo_year.currentIndexChanged.connect(self.refresh_history)
        fbar.addWidget(self.hist_cbo_year)

        self.hist_search = QComboBox()
        self.hist_search.setEditable(True)
        self.hist_search.setFixedWidth(140)
        self.hist_search.lineEdit().setPlaceholderText("🔍 Search...")
        self.hist_search.lineEdit().textChanged.connect(self.refresh_history)
        fbar.addWidget(self.hist_search)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(36)
        btn_refresh.clicked.connect(self.refresh_history)
        fbar.addWidget(btn_refresh)

        fbar.addStretch()

        btn_export_all = QPushButton("📊  Export Excel")
        btn_export_all.setObjectName("btn_secondary")
        btn_export_all.clicked.connect(self._export_all_excel)
        fbar.addWidget(btn_export_all)
        rv.addLayout(fbar)

        # Table
        self.hist_table = QTableWidget()
        self.hist_table.setColumnCount(8)
        self.hist_table.setHorizontalHeaderLabels([
            "Invoice No", "Company", "Period", "Total Prints",
            "Sub Total", "Tax", "Total Amount", "Status"
        ])
        self.hist_table.setAlternatingRowColors(True)
        self.hist_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.hist_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.hist_table.verticalHeader().setVisible(False)
        self.hist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.hist_table.setColumnWidth(0, 140)
        self.hist_table.setColumnWidth(2, 110)
        self.hist_table.setColumnWidth(3, 90)
        self.hist_table.setColumnWidth(4, 100)
        self.hist_table.setColumnWidth(5, 80)
        self.hist_table.setColumnWidth(6, 110)
        self.hist_table.setColumnWidth(7, 80)
        rv.addWidget(self.hist_table)

        # Action bar
        act = QHBoxLayout()
        act.addStretch()

        btn_view_pdf = QPushButton("👁️  Open PDF")
        btn_view_pdf.clicked.connect(self._open_pdf)
        act.addWidget(btn_view_pdf)

        btn_dl_pdf = QPushButton("📥  Download PDF")
        btn_dl_pdf.setObjectName("btn_success")
        btn_dl_pdf.clicked.connect(self._download_pdf)
        act.addWidget(btn_dl_pdf)

        btn_ex_inv = QPushButton("📊  Export Invoice Excel")
        btn_ex_inv.setObjectName("btn_secondary")
        btn_ex_inv.clicked.connect(self._export_invoice_excel)
        act.addWidget(btn_ex_inv)

        btn_del_inv = QPushButton("🗑️  Delete Invoice")
        btn_del_inv.setObjectName("btn_danger")
        btn_del_inv.clicked.connect(self._delete_invoice)
        act.addWidget(btn_del_inv)
        rv.addLayout(act)

        # Stats row
        self.hist_stats = QLabel()
        self.hist_stats.setStyleSheet("color:#6c757d; font-size:12px;")
        rv.addWidget(self.hist_stats)

        main.addWidget(right, stretch=1)

    # ------------------------------------------------------------------ #
    #  Populate selectors                                                  #
    # ------------------------------------------------------------------ #

    def _populate_selectors(self):
        companies = self.db.get_all_companies()

        # Generate-bill company
        self.cbo_company.clear()
        self.cbo_company.addItem("-- Select Company --", None)
        for c in companies:
            self.cbo_company.addItem(c['name'], c['id'])

        # History filter company
        self.hist_cbo_company.clear()
        self.hist_cbo_company.addItem("All Companies", None)
        for c in companies:
            self.hist_cbo_company.addItem(c['name'], c['id'])

    def reload_companies(self):
        self._populate_selectors()
        self.refresh_history()

    # ------------------------------------------------------------------ #
    #  GST toggle                                                          #
    # ------------------------------------------------------------------ #

    def _on_gst_toggle(self):
        cgst_sgst = self.rb_cgst.isChecked()
        igst      = self.rb_igst.isChecked()
        self.spin_cgst.setEnabled(cgst_sgst)
        self.spin_sgst.setEnabled(cgst_sgst)
        self.spin_igst.setEnabled(igst)

    def _gst_type(self) -> str:
        if self.rb_cgst.isChecked(): return BillingService.GST_CGST_SGST
        if self.rb_igst.isChecked(): return BillingService.GST_IGST
        return BillingService.GST_NONE

    # ------------------------------------------------------------------ #
    #  Preview                                                             #
    # ------------------------------------------------------------------ #

    def _add_extra_row(self, description='', extra_type='charge',
                      amount=0.0, taxable=True):
        """
        Add a row to the extras QTableWidget.
        Uses cell widgets (QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox)
        which are owned by the table — no manual deletion needed.
        """
        tbl = self.extras_table
        row = tbl.rowCount()
        tbl.insertRow(row)
        tbl.setRowHeight(row, 40)

        # Col 0 — description
        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("e.g. Service Charge")
        desc_edit.setText(str(description))
        desc_edit.setFrame(False)
        desc_edit.setStyleSheet("padding: 2px 6px; font-size:12px;")
        tbl.setCellWidget(row, 0, desc_edit)

        # Col 1 — type
        type_cbo = QComboBox()
        type_cbo.addItem("+ Charge",   "charge")
        type_cbo.addItem("- Discount", "discount")
        type_cbo.setCurrentIndex(0 if extra_type == "charge" else 1)
        type_cbo.setStyleSheet("font-weight:600; font-size:12px;")
        tbl.setCellWidget(row, 1, type_cbo)

        # Col 2 — amount
        amt_spin = QDoubleSpinBox()
        amt_spin.setRange(0.0, 9_999_999.0)
        amt_spin.setDecimals(2)
        amt_spin.setSingleStep(100.0)
        amt_spin.setValue(float(amount))
        amt_spin.setPrefix("Rs ")
        amt_spin.setFrame(False)
        amt_spin.setStyleSheet("font-size:13px; font-weight:600;")
        tbl.setCellWidget(row, 2, amt_spin)

        # Col 3 — taxable checkbox (centred)
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.setContentsMargins(0, 0, 0, 0)
        chk_layout.setAlignment(Qt.AlignCenter)
        tax_chk = QCheckBox()
        tax_chk.setChecked(bool(taxable))
        tax_chk.setToolTip("Tick = this amount is included in the GST taxable base")
        chk_layout.addWidget(tax_chk)
        tbl.setCellWidget(row, 3, chk_widget)

    def _remove_extra_row(self):
        """Remove the currently selected row from the extras table."""
        tbl = self.extras_table
        row = tbl.currentRow()
        if row >= 0:
            tbl.removeRow(row)
        elif tbl.rowCount() > 0:
            tbl.removeRow(tbl.rowCount() - 1)

    def _collect_extras(self) -> list:
        """Read all extras rows from the QTableWidget and return as list of dicts."""
        extras = []
        tbl = self.extras_table
        for row in range(tbl.rowCount()):
            desc_w = tbl.cellWidget(row, 0)
            type_w = tbl.cellWidget(row, 1)
            amt_w  = tbl.cellWidget(row, 2)
            chk_container = tbl.cellWidget(row, 3)

            if not (desc_w and type_w and amt_w and chk_container):
                continue

            desc = desc_w.text().strip()
            amt  = amt_w.value()
            if not desc or amt <= 0:
                continue

            # Find the QCheckBox inside the container widget
            tax_chk = chk_container.findChild(QCheckBox)
            taxable = tax_chk.isChecked() if tax_chk else True

            extras.append({
                'description': desc,
                'extra_type':  type_w.currentData(),
                'amount':      amt,
                'taxable':     taxable,
            })
        return extras

    def _calculate_preview(self):
        company_id = self.cbo_company.currentData()
        month      = self.cbo_month.currentData()
        year       = self.cbo_year.currentData()

        if not company_id:
            QMessageBox.warning(self, "Select Company", "Please select a company.")
            return

        try:
            preview = self.billing.calculate_bill(
                company_id, month, year,
                gst_type=self._gst_type(),
                custom_cgst=self.spin_cgst.value(),
                custom_sgst=self.spin_sgst.value(),
                custom_igst=self.spin_igst.value(),
                extras=self._collect_extras(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Cannot Generate", str(e))
            self.preview_text.setHtml(f"<span style='color:red;'>{e}</span>")
            self.btn_generate.setEnabled(False)
            self._preview_data = None
            return

        self._preview_data = preview
        self._render_preview(preview)
        self.btn_generate.setEnabled(True)

    def _render_preview(self, p: dict):
        lines = [
            f"<b>Company:</b>  {p['company_name']}",
            f"<b>Period:</b>   {month_year_label(p['month'], p['year'])}",
            f"<b>Invoice No:</b> {p['invoice_number']}",
            "─" * 42,
        ]
        for item in p['items']:
            lines.append(
                f"  {item['printer_serial']:15s}  "
                f"{item['total_prints']:>8,} prints  "
                f"Rs {item['amount']:>10,.2f}"
            )
        lines += [
            "─" * 42,
            f"<b>Print Charges: Rs {p['subtotal']:>12,.2f}</b>",
        ]
        # Extras
        for ex in p.get('extras', []):
            sign  = "+" if ex['extra_type'] == 'charge' else "-"
            taxed = "* " if ex.get('taxable', True) else "  "
            lines.append(
                f"  {sign} {taxed}{ex['description'][:22]:22s}  "
                f"Rs {ex['amount']:>10,.2f}"
            )
        if p.get('cgst_amount'):
            lines.append(f"  CGST {p['cgst_rate']:.1f}%:          Rs {p['cgst_amount']:>10,.2f}")
        if p.get('sgst_amount'):
            lines.append(f"  SGST {p['sgst_rate']:.1f}%:          Rs {p['sgst_amount']:>10,.2f}")
        if p.get('igst_amount'):
            lines.append(f"  IGST {p['igst_rate']:.1f}%:          Rs {p['igst_amount']:>10,.2f}")
        lines += [
            "═" * 42,
            f"<b style='color:#27ae60;'>TOTAL:          Rs {p['total_amount']:>12,.2f}</b>",
        ]
        if p.get('extras'):
            lines.append("<i style='color:#888;font-size:10px;'>* included in GST base</i>")
        self.preview_text.setHtml("<pre style='font-family:Courier New;font-size:11px;'>"
                                   + "\n".join(lines) + "</pre>")

    # ------------------------------------------------------------------ #
    #  Generate invoice                                                    #
    # ------------------------------------------------------------------ #

    def _generate_invoice(self):
        if not self._preview_data:
            return

        # Save to DB
        try:
            invoice_id = self.billing.finalise_bill(self._preview_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save invoice:\n{e}")
            return

        # Generate PDF
        inv = self.db.get_invoice(invoice_id)
        company_name = inv['company_name'].replace(' ', '_').replace('/', '-')
        period_str   = f"{month_year_label(inv['month'], inv['year']).replace(' ','_')}"
        fname        = f"Invoice_{inv['invoice_number'].replace('/','_')}_{company_name}_{period_str}.pdf"
        out_dir      = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "invoices")
        out_path     = os.path.join(out_dir, fname)

        try:
            self.pdf_svc.generate_invoice(inv, out_path)
            self.db.update_invoice_pdf_path(invoice_id, out_path)
        except Exception as e:
            QMessageBox.warning(self, "PDF Error",
                f"Invoice saved but PDF generation failed:\n{e}")
        else:
            reply = QMessageBox.information(
                self, "Invoice Generated",
                f"✅ Invoice <b>{inv['invoice_number']}</b> generated successfully!<br><br>"
                f"PDF saved to:<br>{out_path}<br><br>"
                "Would you like to open the PDF now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._open_file(out_path)

        self._preview_data = None
        self.btn_generate.setEnabled(False)
        self.preview_text.clear()
        self.refresh_history()

    # ------------------------------------------------------------------ #
    #  History operations                                                  #
    # ------------------------------------------------------------------ #

    def refresh_history(self):
        company_id = self.hist_cbo_company.currentData()
        year       = self.hist_cbo_year.currentData()
        search     = (self.hist_search.lineEdit().text().strip()
                      if self.hist_search.lineEdit() else '')

        invoices = self.db.get_all_invoices(company_id=company_id,
                                             year=year, search=search)
        self.hist_table.setRowCount(len(invoices))

        total_amount = 0.0
        for row, inv in enumerate(invoices):
            tax = inv['cgst_amount'] + inv['sgst_amount'] + inv['igst_amount']
            data = [
                (inv['invoice_number'],                     Qt.AlignLeft | Qt.AlignVCenter),
                (inv['company_name'],                       Qt.AlignLeft | Qt.AlignVCenter),
                (month_year_label(inv['month'], inv['year']), Qt.AlignCenter),
                (f"{inv['total_prints']:,}",                Qt.AlignRight | Qt.AlignVCenter),
                (f"₹ {inv['subtotal']:,.2f}",              Qt.AlignRight | Qt.AlignVCenter),
                (f"₹ {tax:,.2f}",                          Qt.AlignRight | Qt.AlignVCenter),
                (f"₹ {inv['total_amount']:,.2f}",          Qt.AlignRight | Qt.AlignVCenter),
                (inv['status'].title(),                     Qt.AlignCenter),
            ]
            for col, (text, align) in enumerate(data):
                item = QTableWidgetItem(text)
                item.setTextAlignment(align)
                if col == 0:
                    item.setData(Qt.UserRole, inv['id'])
                self.hist_table.setItem(row, col, item)
            total_amount += inv['total_amount']

        self.hist_stats.setText(
            f"{len(invoices)} invoice(s)  |  Total: ₹ {total_amount:,.2f}"
        )

    def _selected_invoice_id(self) -> int | None:
        row = self.hist_table.currentRow()
        if row < 0:
            return None
        item = self.hist_table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _open_pdf(self):
        inv_id = self._selected_invoice_id()
        if not inv_id:
            QMessageBox.information(self, "Select", "Please select an invoice.")
            return
        inv = self.db.get_invoice(inv_id)
        pdf_path = inv.get('pdf_path', '')
        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.warning(self, "PDF Missing",
                "PDF file not found. Try regenerating the invoice.")
            return
        self._open_file(pdf_path)

    def _download_pdf(self):
        inv_id = self._selected_invoice_id()
        if not inv_id:
            QMessageBox.information(self, "Select", "Please select an invoice.")
            return
        inv = self.db.get_invoice(inv_id)
        pdf_path = inv.get('pdf_path', '')
        if not pdf_path or not os.path.exists(pdf_path):
            # Regenerate
            try:
                company_name = inv['company_name'].replace(' ', '_').replace('/', '-')
                period_str   = month_year_label(inv['month'], inv['year']).replace(' ', '_')
                fname   = f"Invoice_{inv['invoice_number'].replace('/','_')}_{company_name}_{period_str}.pdf"
                out_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "invoices"
                )
                pdf_path = os.path.join(out_dir, fname)
                self.pdf_svc.generate_invoice(inv, pdf_path)
                self.db.update_invoice_pdf_path(inv_id, pdf_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to generate PDF:\n{e}")
                return

        dest, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", os.path.basename(pdf_path), "PDF Files (*.pdf)"
        )
        if dest:
            import shutil
            shutil.copy2(pdf_path, dest)
            QMessageBox.information(self, "Saved", f"PDF saved to:\n{dest}")

    def _export_invoice_excel(self):
        inv_id = self._selected_invoice_id()
        if not inv_id:
            QMessageBox.information(self, "Select", "Please select an invoice.")
            return
        inv  = self.db.get_invoice(inv_id)
        fname = f"Invoice_{inv['invoice_number'].replace('/','_')}.xlsx"
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Excel As", fname, "Excel Files (*.xlsx)"
        )
        if dest:
            try:
                self.excel_svc.export_invoice(inv_id, dest)
                QMessageBox.information(self, "Exported", f"Exported to:\n{dest}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _export_all_excel(self):
        company_id = self.hist_cbo_company.currentData()
        year       = self.hist_cbo_year.currentData()
        fname      = f"Invoices_Summary_{year or 'All'}.xlsx"
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Summary Excel", fname, "Excel Files (*.xlsx)"
        )
        if dest:
            try:
                self.excel_svc.export_invoices_summary(dest,
                    company_id=company_id, year=year)
                QMessageBox.information(self, "Exported", f"Exported to:\n{dest}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _delete_invoice(self):
        inv_id = self._selected_invoice_id()
        if not inv_id:
            QMessageBox.information(self, "Select", "Please select an invoice.")
            return
        inv = self.db.get_invoice(inv_id)
        msg = (f"Delete invoice <b>{inv['invoice_number']}</b>?<br><br>"
               f"Company: {inv['company_name']}<br>"
               f"Period: {month_year_label(inv['month'], inv['year'])}<br><br>"
               "<b>Counter readings will NOT be deleted (you can regenerate later).</b>")
        reply = QMessageBox.question(self, "Confirm Delete", msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.delete_invoice(inv_id)
            self.refresh_history()

    # ------------------------------------------------------------------ #
    #  File opener (cross-platform)                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _open_file(path: str):
        try:
            if platform.system() == 'Windows':
                os.startfile(path)
            elif platform.system() == 'Darwin':
                subprocess.run(['open', path], check=True)
            else:
                subprocess.run(['xdg-open', path], check=True)
        except Exception as e:
            QMessageBox.warning(None, "Cannot Open",
                f"Could not open file automatically:\n{path}\n\nError: {e}")
