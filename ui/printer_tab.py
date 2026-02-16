"""
ui/printer_tab.py
==================
Tab widget for Printer management.
Features:
  - Filter by company
  - Show/hide inactive printers
  - Add / Edit / Delete / Toggle Active
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QComboBox,
    QDialog, QFormLayout, QDialogButtonBox, QMessageBox, QCheckBox,
    QAbstractItemView, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui  import QColor

from utils.helpers import safe_int


# ============================================================================
#  Printer CRUD Dialog
# ============================================================================

class PrinterDialog(QDialog):
    def __init__(self, parent=None, companies: list = None,
                 printer: dict = None, preselect_company: int = None):
        super().__init__(parent)
        self.companies = companies or []
        self.printer   = printer
        self.setWindowTitle("Edit Printer" if printer else "Add Printer")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._build_ui(preselect_company)
        if printer:
            self._populate(printer)

    def _build_ui(self, preselect_company):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Edit Printer" if self.printer else "Add New Printer")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#1a3c5e;")
        layout.addWidget(title)

        form = QGroupBox("Printer Details")
        fl   = QFormLayout(form)
        fl.setSpacing(10)
        fl.setLabelAlignment(Qt.AlignRight)

        # Company selector (hidden when editing)
        self.cbo_company = QComboBox()
        for c in self.companies:
            self.cbo_company.addItem(c['name'], c['id'])
        if preselect_company:
            for i in range(self.cbo_company.count()):
                if self.cbo_company.itemData(i) == preselect_company:
                    self.cbo_company.setCurrentIndex(i)
                    break

        self.e_pid    = QLineEdit(); self.e_pid.setPlaceholderText("Unique printer serial / ID *")
        self.e_name   = QLineEdit(); self.e_name.setPlaceholderText("e.g. HP LaserJet M1005")
        self.e_model  = QLineEdit(); self.e_model.setPlaceholderText("Model number")
        self.e_loc    = QLineEdit(); self.e_loc.setPlaceholderText("Floor 2 - Accounts Dept")
        self.chk_active = QCheckBox("Active")
        self.chk_active.setChecked(True)

        fl.addRow("Company *:",     self.cbo_company)
        fl.addRow("Printer ID *:",  self.e_pid)
        fl.addRow("Printer Name:",  self.e_name)
        fl.addRow("Model:",         self.e_model)
        fl.addRow("Location:",      self.e_loc)
        fl.addRow("Status:",        self.chk_active)
        layout.addWidget(form)

        # Disable company when editing
        if self.printer:
            self.cbo_company.setEnabled(False)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setText("💾  Save")
        btns.button(QDialogButtonBox.Cancel).setText("✕  Cancel")
        layout.addWidget(btns)

    def _populate(self, p: dict):
        # Set company
        for i in range(self.cbo_company.count()):
            if self.cbo_company.itemData(i) == p['company_id']:
                self.cbo_company.setCurrentIndex(i)
                break
        self.e_pid.setText(p.get('printer_id', ''))
        self.e_name.setText(p.get('printer_name', ''))
        self.e_model.setText(p.get('model', ''))
        self.e_loc.setText(p.get('location', ''))
        self.chk_active.setChecked(bool(p.get('is_active', 1)))

    def _validate_and_accept(self):
        if not self.cbo_company.currentData():
            QMessageBox.warning(self, "Validation", "Please select a company.")
            return
        if not self.e_pid.text().strip():
            QMessageBox.warning(self, "Validation", "Printer ID is required.")
            self.e_pid.setFocus()
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            'company_id':   self.cbo_company.currentData(),
            'printer_id':   self.e_pid.text().strip(),
            'printer_name': self.e_name.text().strip(),
            'model':        self.e_model.text().strip(),
            'location':     self.e_loc.text().strip(),
            'is_active':    self.chk_active.isChecked(),
        }


# ============================================================================
#  Printer Tab
# ============================================================================

class PrinterTab(QWidget):
    printer_changed = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Top bar ───────────────────────────────────────────────────
        top = QHBoxLayout()

        lbl = QLabel("🖨️  Printers")
        lbl.setStyleSheet("font-size:18px; font-weight:700; color:#1a3c5e;")
        top.addWidget(lbl)
        top.addStretch()

        top.addWidget(QLabel("Company:"))
        self.cbo_filter = QComboBox()
        self.cbo_filter.setFixedWidth(180)
        self.cbo_filter.addItem("All Companies", None)
        self.cbo_filter.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.cbo_filter)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Search printer ID / name ...")
        self.search_box.setFixedWidth(220)
        self.search_box.textChanged.connect(self.refresh)
        top.addWidget(self.search_box)

        self.chk_inactive = QCheckBox("Show inactive")
        self.chk_inactive.stateChanged.connect(self.refresh)
        top.addWidget(self.chk_inactive)

        btn_add = QPushButton("➕  Add Printer")
        btn_add.setObjectName("btn_success")
        btn_add.clicked.connect(self.add_printer)
        top.addWidget(btn_add)
        layout.addLayout(top)

        # ── Table ─────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Company", "Printer ID", "Printer Name",
            "Model", "Location", "Status", "Created"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 130)
        self.table.setColumnWidth(6, 70)
        self.table.setColumnWidth(7, 100)
        self.table.doubleClicked.connect(self.edit_printer)
        layout.addWidget(self.table)

        # ── Action buttons ────────────────────────────────────────────
        bot = QHBoxLayout()
        bot.addStretch()

        btn_toggle = QPushButton("🔄  Toggle Active")
        btn_toggle.setObjectName("btn_warning")
        btn_toggle.clicked.connect(self.toggle_active)
        bot.addWidget(btn_toggle)

        btn_edit = QPushButton("✏️  Edit")
        btn_edit.clicked.connect(self.edit_printer)
        bot.addWidget(btn_edit)

        btn_del = QPushButton("🗑️  Delete")
        btn_del.setObjectName("btn_danger")
        btn_del.clicked.connect(self.delete_printer)
        bot.addWidget(btn_del)
        layout.addLayout(bot)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color:#6c757d; font-size:12px;")
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------------ #

    def reload_companies(self):
        """Called externally when companies change."""
        current = self.cbo_filter.currentData()
        self.cbo_filter.blockSignals(True)
        self.cbo_filter.clear()
        self.cbo_filter.addItem("All Companies", None)
        for c in self.db.get_all_companies():
            self.cbo_filter.addItem(c['name'], c['id'])
        # Restore selection
        for i in range(self.cbo_filter.count()):
            if self.cbo_filter.itemData(i) == current:
                self.cbo_filter.setCurrentIndex(i)
                break
        self.cbo_filter.blockSignals(False)
        self.refresh()

    def refresh(self):
        search      = self.search_box.text().strip()
        company_id  = self.cbo_filter.currentData()
        show_inactive = self.chk_inactive.isChecked()

        if company_id:
            rows = self.db.get_printers_by_company(company_id,
                                                    active_only=not show_inactive)
            # Attach company name
            c = self.db.get_company(company_id)
            cname = c['name'] if c else ''
            for r in rows:
                r['company_name'] = cname
            if search:
                s = search.lower()
                rows = [r for r in rows
                        if s in r['printer_id'].lower()
                        or s in r.get('printer_name','').lower()
                        or s in r.get('location','').lower()]
        else:
            all_rows = self.db.get_all_printers(search=search)
            if not show_inactive:
                all_rows = [r for r in all_rows if r['is_active']]
            rows = all_rows

        self.table.setRowCount(len(rows))
        for row, p in enumerate(rows):
            active = bool(p.get('is_active', 1))
            data   = [
                (str(p['id']),                    Qt.AlignCenter),
                (p.get('company_name',''),         Qt.AlignLeft | Qt.AlignVCenter),
                (p['printer_id'],                  Qt.AlignLeft | Qt.AlignVCenter),
                (p.get('printer_name',''),         Qt.AlignLeft | Qt.AlignVCenter),
                (p.get('model',''),                Qt.AlignLeft | Qt.AlignVCenter),
                (p.get('location',''),             Qt.AlignLeft | Qt.AlignVCenter),
                ('✅ Active' if active else '❌ Inactive', Qt.AlignCenter),
                ((p.get('created_at','') or '')[:10], Qt.AlignCenter),
            ]
            for col, (text, align) in enumerate(data):
                item = QTableWidgetItem(text)
                item.setTextAlignment(align)
                if col == 0:
                    item.setData(Qt.UserRole, p['id'])
                if not active:
                    item.setForeground(QColor('#adb5bd'))
                self.table.setItem(row, col, item)

        total   = len(rows)
        active_n = sum(1 for r in rows if r.get('is_active', 1))
        self.status_label.setText(f"{total} printer(s) — {active_n} active")

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def add_printer(self):
        companies = self.db.get_all_companies()
        if not companies:
            QMessageBox.warning(self, "No Companies",
                "Please add at least one company first.")
            return
        preselect = self.cbo_filter.currentData()
        dlg = PrinterDialog(self, companies=companies, preselect_company=preselect)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                self.db.add_printer(
                    data['company_id'], data['printer_id'],
                    data['printer_name'], data['model'], data['location']
                )
                self.refresh()
                self.printer_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "Error",
                    f"Could not add printer.\n{e}\n\nPrinter ID may already exist for this company.")

    def edit_printer(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Select", "Please select a printer to edit.")
            return
        printer = self.db.get_printer(pid)
        companies = self.db.get_all_companies()
        dlg = PrinterDialog(self, companies=companies, printer=printer)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            self.db.update_printer(pid, data['printer_id'], data['printer_name'],
                                   data['model'], data['location'], data['is_active'])
            self.refresh()
            self.printer_changed.emit()

    def toggle_active(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Select", "Please select a printer.")
            return
        printer = self.db.get_printer(pid)
        new_state = not bool(printer.get('is_active', 1))
        self.db.update_printer(pid, printer['printer_id'],
                               printer.get('printer_name',''),
                               printer.get('model',''),
                               printer.get('location',''), new_state)
        self.refresh()
        self.printer_changed.emit()

    def delete_printer(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Select", "Please select a printer to delete.")
            return
        printer = self.db.get_printer(pid)
        msg = (f"Delete printer <b>{printer['printer_id']}</b>?<br><br>"
               "This will also delete all counter readings for this printer.<br>"
               "<b>This action cannot be undone.</b>")
        reply = QMessageBox.question(self, "Confirm Delete", msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.delete_printer(pid)
            self.refresh()
            self.printer_changed.emit()
