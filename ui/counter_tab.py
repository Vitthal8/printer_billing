"""
ui/counter_tab.py
==================
Tab for entering/editing monthly counter readings.

Workflow:
  1. Select Company → Month → Year
  2. Table auto-populates with all active printers
  3. Enter Opening + Closing for each printer
  4. Total Prints is auto-calculated
  5. Save All saves/updates every row atomically
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView, QSpinBox, QFrame, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui  import QColor, QFont

from utils.helpers import MONTHS, current_month, current_year, year_range, month_year_label


class CounterTab(QWidget):
    readings_saved = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._build_ui()
        self._populate_selectors()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Title ─────────────────────────────────────────────────────
        lbl = QLabel("📊  Counter Entry")
        lbl.setStyleSheet("font-size:18px; font-weight:700; color:#1a3c5e;")
        layout.addWidget(lbl)

        # ── Selector row ──────────────────────────────────────────────
        sel_group = QGroupBox("Select Period")
        sel_lay   = QHBoxLayout(sel_group)
        sel_lay.setSpacing(12)

        sel_lay.addWidget(QLabel("Company:"))
        self.cbo_company = QComboBox()
        self.cbo_company.setFixedWidth(200)
        self.cbo_company.currentIndexChanged.connect(self._load_readings)
        sel_lay.addWidget(self.cbo_company)

        sel_lay.addWidget(QLabel("Month:"))
        self.cbo_month = QComboBox()
        self.cbo_month.setFixedWidth(120)
        for i, m in enumerate(MONTHS, start=1):
            self.cbo_month.addItem(m, i)
        self.cbo_month.setCurrentIndex(current_month() - 1)
        self.cbo_month.currentIndexChanged.connect(self._load_readings)
        sel_lay.addWidget(self.cbo_month)

        sel_lay.addWidget(QLabel("Year:"))
        self.cbo_year = QComboBox()
        self.cbo_year.setFixedWidth(90)
        for y in reversed(year_range()):
            self.cbo_year.addItem(str(y), y)
        self.cbo_year.currentIndexChanged.connect(self._load_readings)
        sel_lay.addWidget(self.cbo_year)

        btn_load = QPushButton("🔄  Load")
        btn_load.clicked.connect(self._load_readings)
        sel_lay.addWidget(btn_load)

        sel_lay.addStretch()

        # Invoice status badge
        self.lbl_invoice_status = QLabel()
        self.lbl_invoice_status.setStyleSheet(
            "font-weight:600; font-size:12px; padding:3px 10px; border-radius:4px;"
        )
        sel_lay.addWidget(self.lbl_invoice_status)

        layout.addWidget(sel_group)

        # ── Info label ────────────────────────────────────────────────
        self.lbl_info = QLabel("Select a company and month to load counter readings.")
        self.lbl_info.setStyleSheet("color:#6c757d; font-size:12px; font-style:italic;")
        layout.addWidget(self.lbl_info)

        # ── Table ─────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Printer ID", "Printer Name", "Location",
            "Opening Counter", "Closing Counter", "Total Prints"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)   # row height
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 160)
        self.table.setColumnWidth(5, 130)
        self.table.setStyleSheet("""
            QTableWidget { font-size: 13px; }
            QTableWidget::item { padding: 4px 8px; }
            QSpinBox {
                font-size: 14px;
                font-weight: 600;
                padding: 4px 8px;
                border: 1.5px solid #2e86c1;
                border-radius: 4px;
                background: white;
                min-height: 30px;
            }
            QSpinBox:focus {
                border: 2px solid #1a3c5e;
                background: #eaf3fb;
            }
        """)
        layout.addWidget(self.table)

        # ── Summary row ───────────────────────────────────────────────
        summ = QHBoxLayout()
        self.lbl_total_prints = QLabel("Total Prints: 0")
        self.lbl_total_prints.setStyleSheet(
            "font-size:14px; font-weight:700; color:#1a3c5e;"
        )
        summ.addWidget(self.lbl_total_prints)
        summ.addStretch()

        self.lbl_amount_preview = QLabel("Estimated Amount: ₹ 0.00")
        self.lbl_amount_preview.setStyleSheet(
            "font-size:14px; font-weight:700; color:#27ae60;"
        )
        summ.addWidget(self.lbl_amount_preview)
        layout.addLayout(summ)

        # ── Buttons ───────────────────────────────────────────────────
        bot = QHBoxLayout()
        bot.addStretch()

        btn_clear = QPushButton("🗑️  Clear All")
        btn_clear.setObjectName("btn_secondary")
        btn_clear.clicked.connect(self._clear_all)
        bot.addWidget(btn_clear)

        btn_save = QPushButton("💾  Save All Readings")
        btn_save.setObjectName("btn_success")
        btn_save.clicked.connect(self._save_all)
        bot.addWidget(btn_save)
        layout.addLayout(bot)

    # ------------------------------------------------------------------ #
    #  Population                                                          #
    # ------------------------------------------------------------------ #

    def _populate_selectors(self):
        """Fill company combobox; called at startup and on company change."""
        current = self.cbo_company.currentData()
        self.cbo_company.blockSignals(True)
        self.cbo_company.clear()
        self.cbo_company.addItem("-- Select Company --", None)
        for c in self.db.get_all_companies():
            self.cbo_company.addItem(c['name'], c['id'])
        # Restore
        for i in range(self.cbo_company.count()):
            if self.cbo_company.itemData(i) == current:
                self.cbo_company.setCurrentIndex(i)
                break
        self.cbo_company.blockSignals(False)

    def reload_companies(self):
        self._populate_selectors()

    # ------------------------------------------------------------------ #
    #  Load readings                                                       #
    # ------------------------------------------------------------------ #

    def _load_readings(self):
        company_id = self.cbo_company.currentData()
        month      = self.cbo_month.currentData()
        year       = self.cbo_year.currentData()

        if not company_id:
            self.table.setRowCount(0)
            self._update_summary()
            return

        printers = self.db.get_printers_by_company(company_id, active_only=True)
        if not printers:
            self.lbl_info.setText("No active printers for this company.")
            self.table.setRowCount(0)
            self._update_summary()
            return

        # Check if invoice already exists
        inv_exists = self.db.invoice_exists(company_id, month, year)
        if inv_exists:
            self.lbl_invoice_status.setText("✅ Invoice Generated")
            self.lbl_invoice_status.setStyleSheet(
                "font-weight:600; font-size:12px; padding:3px 10px; "
                "border-radius:4px; background:#d4edda; color:#155724;"
            )
        else:
            self.lbl_invoice_status.setText("📄 No Invoice Yet")
            self.lbl_invoice_status.setStyleSheet(
                "font-weight:600; font-size:12px; padding:3px 10px; "
                "border-radius:4px; background:#fff3cd; color:#856404;"
            )

        self.lbl_info.setText(
            f"Showing {len(printers)} active printer(s) for "
            f"{month_year_label(month, year)}"
        )

        self.table.setRowCount(len(printers))
        self._printer_ids = []   # track printer DB PKs per row

        for row, p in enumerate(printers):
            self._printer_ids.append(p['id'])

            # Fetch existing reading if any
            reading = self.db.get_counter_reading(p['id'], month, year)

            # Read-only columns
            for col, text in enumerate([
                p['printer_id'],
                p.get('printer_name', ''),
                p.get('location', ''),
            ]):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, col, item)

            # Opening counter spinbox
            opening_spin = QSpinBox()
            opening_spin.setRange(0, 99_999_999)
            opening_spin.setGroupSeparatorShown(True)
            opening_spin.setMinimumHeight(34)
            opening_spin.setFont(QFont('Segoe UI', 12))
            if reading:
                opening_spin.setValue(reading['opening_counter'])
            opening_spin.valueChanged.connect(lambda v, r=row: self._on_value_changed(r))
            self.table.setCellWidget(row, 3, opening_spin)

            # Closing counter spinbox
            closing_spin = QSpinBox()
            closing_spin.setRange(0, 99_999_999)
            closing_spin.setGroupSeparatorShown(True)
            closing_spin.setMinimumHeight(34)
            closing_spin.setFont(QFont('Segoe UI', 12))
            if reading:
                closing_spin.setValue(reading['closing_counter'])
            closing_spin.valueChanged.connect(lambda v, r=row: self._on_value_changed(r))
            self.table.setCellWidget(row, 4, closing_spin)

            # Force the row to be tall enough for the spinboxes
            self.table.setRowHeight(row, 42)

            # Total prints — read only, auto-calculated
            total_item = QTableWidgetItem(
                f"{reading['total_prints']:,}" if reading else "0"
            )
            total_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_item.setFont(QFont('Segoe UI', 10, QFont.Bold))
            self.table.setItem(row, 5, total_item)

        self._update_summary()

    def _on_value_changed(self, row: int):
        """Recalculate total for a row when opening/closing changes."""
        opening_w = self.table.cellWidget(row, 3)
        closing_w = self.table.cellWidget(row, 4)
        if not opening_w or not closing_w:
            return
        opening = opening_w.value()
        closing = closing_w.value()
        total   = max(0, closing - opening)

        item = self.table.item(row, 5)
        if item:
            item.setText(f"{total:,}")
            # Highlight negative difference
            if closing < opening:
                item.setForeground(QColor('#c0392b'))
                item.setText(f"⚠️ {total:,}")
            else:
                item.setForeground(QColor('#1a3c5e'))

        self._update_summary()

    def _update_summary(self):
        total = 0
        for row in range(self.table.rowCount()):
            opening_w = self.table.cellWidget(row, 3)
            closing_w = self.table.cellWidget(row, 4)
            if opening_w and closing_w:
                total += max(0, closing_w.value() - opening_w.value())

        self.lbl_total_prints.setText(f"Total Prints: {total:,}")

        # Estimate amount using company rate
        company_id = self.cbo_company.currentData()
        if company_id:
            company = self.db.get_company(company_id)
            if company:
                amount = total * company.get('rate_per_print', 0)
                self.lbl_amount_preview.setText(f"Estimated Amount: ₹ {amount:,.2f}")

    # ------------------------------------------------------------------ #
    #  Save / Clear                                                        #
    # ------------------------------------------------------------------ #

    def _save_all(self):
        company_id = self.cbo_company.currentData()
        month      = self.cbo_month.currentData()
        year       = self.cbo_year.currentData()

        if not company_id:
            QMessageBox.warning(self, "Select Company", "Please select a company first.")
            return
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Printers", "No printers loaded.")
            return

        # Validate: closing >= opening
        errors = []
        for row in range(self.table.rowCount()):
            pid_item = self.table.item(row, 0)
            ow = self.table.cellWidget(row, 3)
            cw = self.table.cellWidget(row, 4)
            if ow and cw and cw.value() < ow.value():
                errors.append(
                    f"Row {row+1} ({pid_item.text() if pid_item else ''}): "
                    "Closing counter is less than Opening counter."
                )

        if errors:
            QMessageBox.warning(self, "Validation Errors",
                "Please fix the following issues:\n\n" + "\n".join(errors))
            return

        # Save each row
        saved = 0
        for row in range(self.table.rowCount()):
            printer_pk = self._printer_ids[row]
            ow = self.table.cellWidget(row, 3)
            cw = self.table.cellWidget(row, 4)
            if ow and cw:
                self.db.save_counter_reading(
                    printer_pk, company_id, month, year,
                    ow.value(), cw.value()
                )
                saved += 1

        QMessageBox.information(self, "Saved",
            f"✅ Counter readings saved for {saved} printer(s).\n"
            f"Period: {month_year_label(month, year)}")
        self.readings_saved.emit()

    def _clear_all(self):
        reply = QMessageBox.question(
            self, "Clear",
            "Clear all entered values in the table?\n(Saved data will not be affected)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for row in range(self.table.rowCount()):
                for col in [3, 4]:
                    w = self.table.cellWidget(row, col)
                    if w:
                        w.setValue(0)
