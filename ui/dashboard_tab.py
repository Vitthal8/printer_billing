"""
ui/dashboard_tab.py
====================
Dashboard: quick stats + recent invoices summary.
Shows stat cards and a monthly revenue bar chart (pure Qt, no matplotlib).
"""

from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy, QGridLayout, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui  import QFont, QColor

from utils.helpers import month_year_label, current_month, current_year


# ============================================================================
#  Stat Card Widget
# ============================================================================

class StatCard(QFrame):
    def __init__(self, icon: str, label: str, value: str,
                 bg: str = "#1a3c5e", text_color: str = "white"):
        super().__init__()
        self.setStyleSheet(
            f"background:{bg}; border-radius:10px; padding:4px;"
        )
        self.setMinimumSize(160, 90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size:22px; background:transparent; color:{text_color};")
        lay.addWidget(icon_lbl)

        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(
            f"font-size:26px; font-weight:800; background:transparent; color:{text_color};"
        )
        lay.addWidget(self.val_lbl)

        lbl_w = QLabel(label)
        lbl_w.setStyleSheet(
            f"font-size:11px; background:transparent; color:{'rgba(255,255,255,0.8)' if text_color=='white' else '#555'};"
        )
        lay.addWidget(lbl_w)

    def update_value(self, value: str):
        self.val_lbl.setText(value)


# ============================================================================
#  Dashboard Tab
# ============================================================================

class DashboardTab(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Greeting ─────────────────────────────────────────────────
        now = datetime.now()
        greet = QLabel(f"👋  Welcome  |  {now.strftime('%A, %d %B %Y')}")
        greet.setStyleSheet("font-size:14px; color:#6c757d; font-weight:500;")
        layout.addWidget(greet)

        title = QLabel("PrintBill Pro — Dashboard")
        title.setStyleSheet("font-size:22px; font-weight:800; color:#1a3c5e;")
        layout.addWidget(title)

        # ── Stat cards row ───────────────────────────────────────────
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self.card_companies = StatCard("🏢", "Total Companies",     "–", "#1a3c5e")
        self.card_printers  = StatCard("🖨️", "Active Printers",     "–", "#2e86c1")
        self.card_invoices  = StatCard("📋", "Total Invoices",      "–", "#27ae60")
        self.card_this_mo   = StatCard("📅", "This Month Invoices", "–", "#8e44ad")
        self.card_revenue   = StatCard("₹",  "This Month Revenue",  "–", "#e67e22",
                                       text_color="white")
        self.card_total_rev = StatCard("💰", "Total Revenue",        "–", "#c0392b")

        for card in [self.card_companies, self.card_printers, self.card_invoices,
                     self.card_this_mo, self.card_revenue, self.card_total_rev]:
            cards_layout.addWidget(card)
        layout.addLayout(cards_layout)

        # ── Two-column lower section ──────────────────────────────────
        lower = QHBoxLayout()
        lower.setSpacing(12)

        # Recent invoices
        rec_grp = QGroupBox("Recent Invoices")
        rec_lay = QVBoxLayout(rec_grp)
        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(5)
        self.recent_table.setHorizontalHeaderLabels(
            ["Invoice No", "Company", "Period", "Total Prints", "Amount (₹)"]
        )
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recent_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.recent_table.setMaximumHeight(240)
        rec_lay.addWidget(self.recent_table)
        lower.addWidget(rec_grp, stretch=2)

        # Monthly summary (current year)
        mo_grp = QGroupBox(f"Monthly Revenue {current_year()}")
        mo_lay = QVBoxLayout(mo_grp)
        self.mo_table = QTableWidget()
        self.mo_table.setColumnCount(3)
        self.mo_table.setHorizontalHeaderLabels(["Month", "Invoices", "Revenue (₹)"])
        self.mo_table.setAlternatingRowColors(True)
        self.mo_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mo_table.verticalHeader().setVisible(False)
        self.mo_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.mo_table.setMaximumHeight(240)
        mo_lay.addWidget(self.mo_table)
        lower.addWidget(mo_grp, stretch=1)

        layout.addLayout(lower)
        layout.addStretch()

        # ── Pending alert ─────────────────────────────────────────────
        self.pending_lbl = QLabel()
        self.pending_lbl.setStyleSheet(
            "background:#fff3cd; color:#856404; border:1px solid #ffc107; "
            "border-radius:6px; padding:8px 14px; font-size:12px; font-weight:600;"
        )
        self.pending_lbl.setWordWrap(True)
        self.pending_lbl.hide()
        layout.addWidget(self.pending_lbl)

    # ------------------------------------------------------------------ #
    #  Refresh                                                             #
    # ------------------------------------------------------------------ #

    def refresh(self):
        stats = self.db.get_dashboard_stats()

        self.card_companies.update_value(str(stats['total_companies']))
        self.card_printers.update_value(str(stats['total_printers']))
        self.card_invoices.update_value(str(stats['total_invoices']))
        self.card_this_mo.update_value(str(stats['current_month_invoices']))
        self.card_revenue.update_value(f"₹ {stats['current_month_revenue']:,.0f}")
        self.card_total_rev.update_value(f"₹ {stats['total_revenue']:,.0f}")

        # Pending entries alert
        pending = stats.get('pending_counter_entries', 0)
        if pending > 0:
            self.pending_lbl.setText(
                f"⚠️  {pending} active printer(s) have no counter reading for "
                f"{month_year_label(current_month(), current_year())}. "
                "Please enter counter readings before generating bills."
            )
            self.pending_lbl.show()
        else:
            self.pending_lbl.hide()

        # Recent invoices (last 10)
        invoices = self.db.get_all_invoices()[:10]
        self.recent_table.setRowCount(len(invoices))
        for row, inv in enumerate(invoices):
            data = [
                inv['invoice_number'],
                inv['company_name'],
                month_year_label(inv['month'], inv['year']),
                f"{inv['total_prints']:,}",
                f"₹ {inv['total_amount']:,.2f}",
            ]
            for col, text in enumerate(data):
                item = QTableWidgetItem(text)
                if col in [3, 4]:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.recent_table.setItem(row, col, item)

        # Monthly summary
        from services.billing_service import BillingService
        svc = BillingService(self.db)
        summary = svc.get_billing_summary(current_year())
        self.mo_table.setRowCount(len(summary))
        for row, s in enumerate(summary):
            items = [
                QTableWidgetItem(s['month_name']),
                QTableWidgetItem(str(s['total_invoices'])),
                QTableWidgetItem(f"₹ {s['total_amount']:,.2f}"),
            ]
            items[1].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            items[2].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Highlight current month
            if s['month'] == current_month():
                for it in items:
                    it.setBackground(QColor('#eaf3fb'))
                    it.setFont(QFont('Segoe UI', 9, QFont.Bold))
            for col, it in enumerate(items):
                self.mo_table.setItem(row, col, it)
