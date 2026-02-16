"""
ui/main_window.py
==================
Top-level application window.
  • QTabWidget with 5 tabs: Dashboard, Companies, Printers, Counter Entry, Billing
  • Toolbar with Settings + About
  • Status bar showing DB path and current period
  • Signal wiring so changes in one tab refresh related tabs
"""

from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QStatusBar, QAction,
    QToolBar, QLabel, QMessageBox, QApplication
)
from PyQt5.QtCore  import Qt, QTimer
from PyQt5.QtGui   import QIcon, QFont

from ui.dashboard_tab    import DashboardTab
from ui.company_tab      import CompanyTab
from ui.printer_tab      import PrinterTab
from ui.counter_tab      import CounterTab
from ui.billing_tab      import BillingTab
from ui.settings_dialog  import SettingsDialog
from utils.helpers       import current_month, current_year, month_year_label


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("PrintBill Pro — Printer Billing Manager")
        self.setMinimumSize(1200, 750)
        self.resize(1320, 820)

        self._build_toolbar()
        self._build_tabs()
        self._build_status_bar()
        self._wire_signals()

        # Periodic status bar clock refresh
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._update_status_bar)
        self._clock.start(60_000)   # every minute

    # ------------------------------------------------------------------ #
    #  Toolbar                                                             #
    # ------------------------------------------------------------------ #

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setStyleSheet(
            "QToolBar { background:#1a3c5e; border:none; padding:4px 8px; spacing:6px; }"
            "QToolBar QLabel { color:white; font-size:16px; font-weight:800; margin-right:16px; }"
            "QToolButton { color:white; background:transparent; padding:5px 12px; "
            "              border-radius:4px; font-size:12px; }"
            "QToolButton:hover { background:#2e86c1; }"
        )

        brand = QLabel("🖨️  PrintBill Pro")
        brand.setFont(QFont("Segoe UI", 13, QFont.Bold))
        tb.addWidget(brand)

        spacer = QWidget(); spacer.setMaximumWidth(20)
        tb.addWidget(spacer)

        refresh_action = QAction("🔄  Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_all)
        tb.addAction(refresh_action)

        settings_action = QAction("⚙️  Settings", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        tb.addAction(settings_action)

        about_action = QAction("ℹ️  About", self)
        about_action.triggered.connect(self._show_about)
        tb.addAction(about_action)

        self.addToolBar(tb)

    # ------------------------------------------------------------------ #
    #  Tabs                                                                #
    # ------------------------------------------------------------------ #

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tab_dashboard = DashboardTab(self.db)
        self.tab_companies = CompanyTab(self.db)
        self.tab_printers  = PrinterTab(self.db)
        self.tab_counters  = CounterTab(self.db)
        self.tab_billing   = BillingTab(self.db)

        self.tabs.addTab(self.tab_dashboard, "🏠  Dashboard")
        self.tabs.addTab(self.tab_companies, "🏢  Companies")
        self.tabs.addTab(self.tab_printers,  "🖨️  Printers")
        self.tabs.addTab(self.tab_counters,  "📊  Counter Entry")
        self.tabs.addTab(self.tab_billing,   "🧾  Billing")

        # Refresh dashboard when switching to it
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self.tabs)

    # ------------------------------------------------------------------ #
    #  Status bar                                                          #
    # ------------------------------------------------------------------ #

    def _build_status_bar(self):
        sb = self.statusBar()
        sb.setStyleSheet(
            "QStatusBar { background:#1a3c5e; color:white; font-size:12px; }"
        )

        self.sb_period = QLabel()
        self.sb_period.setStyleSheet("color:white;")
        sb.addWidget(self.sb_period)

        sb.addPermanentWidget(QLabel("  |  "))

        self.sb_db = QLabel()
        self.sb_db.setStyleSheet("color:#adb5bd;")
        sb.addPermanentWidget(self.sb_db)

        self._update_status_bar()

    def _update_status_bar(self):
        self.sb_period.setText(
            f"  Current Period: {month_year_label(current_month(), current_year())}"
        )
        self.sb_db.setText(f"DB: {self.db.db_path}  ")

    # ------------------------------------------------------------------ #
    #  Signal wiring                                                       #
    # ------------------------------------------------------------------ #

    def _wire_signals(self):
        """Connect cross-tab signals so data stays consistent."""
        # When companies change → refresh printers selector, counter selector, billing selector
        self.tab_companies.company_changed.connect(self.tab_printers.reload_companies)
        self.tab_companies.company_changed.connect(self.tab_counters.reload_companies)
        self.tab_companies.company_changed.connect(self.tab_billing.reload_companies)
        self.tab_companies.company_changed.connect(self.tab_dashboard.refresh)

        # When printers change → refresh counter entry
        self.tab_printers.printer_changed.connect(self.tab_counters.reload_companies)
        self.tab_printers.printer_changed.connect(self.tab_dashboard.refresh)

        # When counter readings saved → refresh billing history + dashboard
        self.tab_counters.readings_saved.connect(self.tab_billing.refresh_history)
        self.tab_counters.readings_saved.connect(self.tab_dashboard.refresh)

    # ------------------------------------------------------------------ #
    #  Tab change handler                                                  #
    # ------------------------------------------------------------------ #

    def _on_tab_changed(self, index: int):
        if index == 0:
            self.tab_dashboard.refresh()
        elif index == 4:
            self.tab_billing.refresh_history()

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    def _refresh_all(self):
        self.tab_dashboard.refresh()
        self.tab_companies.refresh()
        self.tab_printers.refresh()
        self.tab_billing.refresh_history()
        self.statusBar().showMessage("All data refreshed.", 3000)

    def _open_settings(self):
        dlg = SettingsDialog(self, self.db)
        if dlg.exec_():
            self.tab_dashboard.refresh()

    def _show_about(self):
        QMessageBox.about(
            self, "About PrintBill Pro",
            "<h2>🖨️ PrintBill Pro</h2>"
            "<p>Version 1.0.0</p>"
            "<p>Professional printer billing management system.</p>"
            "<ul>"
            "<li>Multi-company, multi-printer support</li>"
            "<li>Monthly counter-based billing</li>"
            "<li>GST-compliant PDF invoices</li>"
            "<li>Excel export for reports</li>"
            "<li>Financial-year-aware invoice numbering</li>"
            "</ul>"
            "<p style='color:#6c757d;'>Built with Python · PyQt5 · ReportLab · openpyxl</p>"
        )
