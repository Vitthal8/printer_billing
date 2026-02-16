"""
ui/company_tab.py
==================
Tab widget for Company management.
Features:
  - Search bar with live filtering
  - Table showing all companies
  - Add / Edit / Delete buttons
  - Company details dialog with validation
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox,
    QMessageBox, QAbstractItemView, QFrame, QGroupBox, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui  import QFont

from utils.helpers import is_valid_gst, safe_float


# ============================================================================
#  Company CRUD Dialog
# ============================================================================

class CompanyDialog(QDialog):
    """Add / Edit company dialog."""

    def __init__(self, parent=None, company: dict | None = None):
        super().__init__(parent)
        self.company = company
        self.setWindowTitle("Edit Company" if company else "Add New Company")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._build_ui()
        if company:
            self._populate(company)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Edit Company" if self.company else "Add New Company")
        title.setObjectName("label_title")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#1a3c5e;")
        layout.addWidget(title)

        # Form
        form = QGroupBox("Company Details")
        fl   = QFormLayout(form)
        fl.setSpacing(10)
        fl.setLabelAlignment(Qt.AlignRight)

        self.e_name    = QLineEdit();  self.e_name.setPlaceholderText("Company name *")
        self.e_address = QTextEdit();  self.e_address.setMaximumHeight(70)
        self.e_address.setPlaceholderText("Full address")
        self.e_gst     = QLineEdit();  self.e_gst.setPlaceholderText("e.g. 27AABCU9603R1ZM")
        self.e_gst.setMaxLength(15)
        self.e_gst.textChanged.connect(lambda t: self.e_gst.setText(t.upper()))
        self.e_rate    = QDoubleSpinBox()
        self.e_rate.setRange(0, 100_000); self.e_rate.setDecimals(4)
        self.e_rate.setPrefix("₹ ");    self.e_rate.setSuffix(" / print")
        self.e_contact = QLineEdit();  self.e_contact.setPlaceholderText("Contact person name")
        self.e_phone   = QLineEdit();  self.e_phone.setPlaceholderText("+91 98765 43210")
        self.e_email   = QLineEdit();  self.e_email.setPlaceholderText("billing@client.com")

        fl.addRow("Company Name *:", self.e_name)
        fl.addRow("Address:",        self.e_address)
        fl.addRow("GST Number:",     self.e_gst)
        fl.addRow("Rate per Print:", self.e_rate)
        fl.addRow("Contact Person:", self.e_contact)
        fl.addRow("Phone:",          self.e_phone)
        fl.addRow("Email:",          self.e_email)
        layout.addWidget(form)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setText("💾  Save")
        btns.button(QDialogButtonBox.Cancel).setText("✕  Cancel")
        layout.addWidget(btns)

    def _populate(self, c: dict):
        self.e_name.setText(c.get('name', ''))
        self.e_address.setPlainText(c.get('address', ''))
        self.e_gst.setText(c.get('gst_number', ''))
        self.e_rate.setValue(safe_float(c.get('rate_per_print', 0)))
        self.e_contact.setText(c.get('contact_person', ''))
        self.e_phone.setText(c.get('contact_phone', ''))
        self.e_email.setText(c.get('email', ''))

    def _validate_and_accept(self):
        name = self.e_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Company name is required.")
            self.e_name.setFocus()
            return
        gst = self.e_gst.text().strip()
        if gst and not is_valid_gst(gst):
            QMessageBox.warning(self, "Validation",
                "Invalid GST number format.\nExpected: 27AABCU9603R1ZM (15 chars)")
            self.e_gst.setFocus()
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            'name':           self.e_name.text().strip(),
            'address':        self.e_address.toPlainText().strip(),
            'gst_number':     self.e_gst.text().strip(),
            'rate_per_print': self.e_rate.value(),
            'contact_person': self.e_contact.text().strip(),
            'contact_phone':  self.e_phone.text().strip(),
            'email':          self.e_email.text().strip(),
        }


# ============================================================================
#  Company Tab
# ============================================================================

class CompanyTab(QWidget):
    """Full company management tab with search + CRUD table."""

    company_changed = pyqtSignal()   # emitted after any add/edit/delete

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Top bar ──────────────────────────────────────────────────
        top = QHBoxLayout()

        lbl = QLabel("🏢  Companies")
        lbl.setStyleSheet("font-size:18px; font-weight:700; color:#1a3c5e;")
        top.addWidget(lbl)
        top.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Search by name, GST ...")
        self.search_box.setFixedWidth(260)
        self.search_box.textChanged.connect(self.refresh)
        top.addWidget(self.search_box)

        btn_add = QPushButton("➕  Add Company")
        btn_add.setObjectName("btn_success")
        btn_add.clicked.connect(self.add_company)
        top.addWidget(btn_add)
        layout.addLayout(top)

        # ── Table ─────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Company Name", "GST Number",
            "Rate / Print (₹)", "Contact Person", "Phone", "Printers"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(2, 165)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 140)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 70)
        self.table.doubleClicked.connect(self.edit_company)
        layout.addWidget(self.table)

        # ── Action buttons ────────────────────────────────────────────
        bot = QHBoxLayout()
        bot.addStretch()
        btn_edit = QPushButton("✏️  Edit")
        btn_edit.clicked.connect(self.edit_company)
        bot.addWidget(btn_edit)

        btn_del  = QPushButton("🗑️  Delete")
        btn_del.setObjectName("btn_danger")
        btn_del.clicked.connect(self.delete_company)
        bot.addWidget(btn_del)
        layout.addLayout(bot)

        # ── Status label ─────────────────────────────────────────────
        self.status_label = QLabel("0 companies")
        self.status_label.setStyleSheet("color:#6c757d; font-size:12px;")
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------------ #
    #  Data operations                                                     #
    # ------------------------------------------------------------------ #

    def refresh(self):
        search = self.search_box.text().strip()
        companies = self.db.get_all_companies(search=search)
        self.table.setRowCount(len(companies))

        for row, c in enumerate(companies):
            # Count printers
            printers = self.db.get_printers_by_company(c['id'])
            n_printers = len(printers)

            items = [
                (str(c['id']),               Qt.AlignCenter),
                (c['name'],                  Qt.AlignLeft | Qt.AlignVCenter),
                (c.get('gst_number',''),     Qt.AlignCenter),
                (f"₹ {c['rate_per_print']:.4f}", Qt.AlignRight | Qt.AlignVCenter),
                (c.get('contact_person',''), Qt.AlignLeft | Qt.AlignVCenter),
                (c.get('contact_phone',''),  Qt.AlignCenter),
                (str(n_printers),            Qt.AlignCenter),
            ]
            for col, (text, align) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(align)
                if col == 0:
                    item.setData(Qt.UserRole, c['id'])
                self.table.setItem(row, col, item)

        self.status_label.setText(f"{len(companies)} company(ies) found")

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def add_company(self):
        dlg = CompanyDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            self.db.add_company(**data)
            self.refresh()
            self.company_changed.emit()

    def edit_company(self):
        cid = self._selected_id()
        if not cid:
            QMessageBox.information(self, "Select", "Please select a company to edit.")
            return
        company = self.db.get_company(cid)
        dlg = CompanyDialog(self, company=company)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            self.db.update_company(cid, **data)
            self.refresh()
            self.company_changed.emit()

    def delete_company(self):
        cid = self._selected_id()
        if not cid:
            QMessageBox.information(self, "Select", "Please select a company to delete.")
            return
        company = self.db.get_company(cid)
        printers = self.db.get_printers_by_company(cid)
        msg = (f"Delete <b>{company['name']}</b>?<br><br>"
               f"This will also delete <b>{len(printers)} printer(s)</b> "
               f"and all their counter readings and invoices.<br><br>"
               f"<b>This action cannot be undone.</b>")
        reply = QMessageBox.question(
            self, "Confirm Delete", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_company(cid)
            self.refresh()
            self.company_changed.emit()
