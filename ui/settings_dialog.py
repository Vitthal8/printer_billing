"""
ui/settings_dialog.py
======================
Application settings dialog.
Groups:
  1. Your Company Details (used in invoice header)
  2. Invoice Numbering
  3. GST Defaults
  4. Logo
"""

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox,
    QGroupBox, QDoubleSpinBox, QSpinBox, QFileDialog,
    QTabWidget, QWidget, QMessageBox
)
from PyQt5.QtCore  import Qt
from PyQt5.QtGui   import QPixmap


class SettingsDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("⚙️  Settings")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("Application Settings")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#1a3c5e;")
        layout.addWidget(title)

        tabs = QTabWidget()

        # ── Tab 1: Company ────────────────────────────────────────────
        t1 = QWidget()
        t1l = QVBoxLayout(t1)
        grp1 = QGroupBox("Your Company (appears on invoice header)")
        fl1  = QFormLayout(grp1)
        fl1.setSpacing(8)
        fl1.setLabelAlignment(Qt.AlignRight)

        self.e_my_name    = QLineEdit()
        self.e_my_addr    = QTextEdit(); self.e_my_addr.setMaximumHeight(70)
        self.e_my_phone   = QLineEdit()
        self.e_my_email   = QLineEdit()
        self.e_my_gst     = QLineEdit()
        self.e_my_gst.setMaxLength(15)
        self.e_my_gst.textChanged.connect(lambda t: self.e_my_gst.setText(t.upper()))
        self.e_terms      = QTextEdit(); self.e_terms.setMaximumHeight(70)

        fl1.addRow("Company Name:",  self.e_my_name)
        fl1.addRow("Address:",       self.e_my_addr)
        fl1.addRow("Phone:",         self.e_my_phone)
        fl1.addRow("Email:",         self.e_my_email)
        fl1.addRow("GSTIN:",         self.e_my_gst)
        fl1.addRow("Terms:",         self.e_terms)
        t1l.addWidget(grp1)
        t1l.addStretch()
        tabs.addTab(t1, "🏢  My Company")

        # ── Tab 2: Invoice / Logo ─────────────────────────────────────
        t2  = QWidget()
        t2l = QVBoxLayout(t2)

        grp2 = QGroupBox("Invoice Numbering")
        fl2  = QFormLayout(grp2)
        fl2.setSpacing(8)
        fl2.setLabelAlignment(Qt.AlignRight)

        self.e_prefix   = QLineEdit(); self.e_prefix.setMaxLength(10)
        self.spin_fy    = QSpinBox(); self.spin_fy.setRange(1, 12)
        self.spin_fy.setPrefix("Month "); self.spin_fy.setSuffix(" (April=4)")

        fl2.addRow("Invoice Prefix:", self.e_prefix)
        fl2.addRow("FY Start Month:", self.spin_fy)
        t2l.addWidget(grp2)

        grp3 = QGroupBox("Logo")
        g3l  = QHBoxLayout(grp3)
        self.e_logo = QLineEdit(); self.e_logo.setReadOnly(True)
        self.e_logo.setPlaceholderText("No logo selected")
        g3l.addWidget(self.e_logo)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_logo)
        g3l.addWidget(btn_browse)
        btn_clear_logo = QPushButton("Clear")
        btn_clear_logo.clicked.connect(lambda: self.e_logo.clear())
        g3l.addWidget(btn_clear_logo)
        t2l.addWidget(grp3)

        # Logo preview
        self.logo_preview = QLabel("No logo")
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_preview.setMinimumHeight(60)
        self.logo_preview.setStyleSheet(
            "background:#f0f4f8; border:1px dashed #cdd5dc; border-radius:4px;"
        )
        t2l.addWidget(self.logo_preview)
        t2l.addStretch()
        tabs.addTab(t2, "🔢  Invoice & Logo")

        # ── Tab 3: GST ────────────────────────────────────────────────
        t3  = QWidget()
        t3l = QVBoxLayout(t3)

        grp4 = QGroupBox("Default GST Rates")
        fl4  = QFormLayout(grp4)
        fl4.setSpacing(8)
        fl4.setLabelAlignment(Qt.AlignRight)

        self.spin_cgst = QDoubleSpinBox(); self.spin_cgst.setRange(0, 28)
        self.spin_cgst.setSuffix(" %"); self.spin_cgst.setDecimals(2)
        self.spin_sgst = QDoubleSpinBox(); self.spin_sgst.setRange(0, 28)
        self.spin_sgst.setSuffix(" %"); self.spin_sgst.setDecimals(2)
        self.spin_igst = QDoubleSpinBox(); self.spin_igst.setRange(0, 28)
        self.spin_igst.setSuffix(" %"); self.spin_igst.setDecimals(2)

        fl4.addRow("Default CGST %:", self.spin_cgst)
        fl4.addRow("Default SGST %:", self.spin_sgst)
        fl4.addRow("Default IGST %:", self.spin_igst)
        t3l.addWidget(grp4)
        t3l.addStretch()
        tabs.addTab(t3, "💰  GST")

        layout.addWidget(tabs)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setText("💾  Save Settings")
        btns.button(QDialogButtonBox.Cancel).setText("✕  Cancel")
        layout.addWidget(btns)

    def _load(self):
        s = self.db.get_all_settings()
        self.e_my_name.setText(s.get('my_company_name', ''))
        self.e_my_addr.setPlainText(s.get('my_company_address', ''))
        self.e_my_phone.setText(s.get('my_company_phone', ''))
        self.e_my_email.setText(s.get('my_company_email', ''))
        self.e_my_gst.setText(s.get('my_company_gst', ''))
        self.e_terms.setPlainText(s.get('terms', ''))
        self.e_prefix.setText(s.get('invoice_prefix', 'INV'))
        self.spin_fy.setValue(int(s.get('financial_year_start', 4)))
        self.spin_cgst.setValue(float(s.get('default_cgst_rate', 9)))
        self.spin_sgst.setValue(float(s.get('default_sgst_rate', 9)))
        self.spin_igst.setValue(float(s.get('default_igst_rate', 18)))
        logo = s.get('logo_path', '')
        if logo:
            self.e_logo.setText(logo)
            self._show_logo_preview(logo)

    def _save(self):
        name = self.e_my_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Company name is required.")
            return

        pairs = [
            ('my_company_name',     name),
            ('my_company_address',  self.e_my_addr.toPlainText().strip()),
            ('my_company_phone',    self.e_my_phone.text().strip()),
            ('my_company_email',    self.e_my_email.text().strip()),
            ('my_company_gst',      self.e_my_gst.text().strip()),
            ('terms',               self.e_terms.toPlainText().strip()),
            ('invoice_prefix',      self.e_prefix.text().strip() or 'INV'),
            ('financial_year_start',str(self.spin_fy.value())),
            ('default_cgst_rate',   str(self.spin_cgst.value())),
            ('default_sgst_rate',   str(self.spin_sgst.value())),
            ('default_igst_rate',   str(self.spin_igst.value())),
            ('logo_path',           self.e_logo.text().strip()),
        ]
        for key, val in pairs:
            self.db.set_setting(key, val)

        QMessageBox.information(self, "Saved", "✅ Settings saved successfully.")
        self.accept()

    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.e_logo.setText(path)
            self._show_logo_preview(path)

    def _show_logo_preview(self, path: str):
        if os.path.exists(path):
            pix = QPixmap(path).scaledToHeight(50, Qt.SmoothTransformation)
            self.logo_preview.setPixmap(pix)
        else:
            self.logo_preview.setText("File not found")
