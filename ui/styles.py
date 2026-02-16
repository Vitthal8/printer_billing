"""
ui/styles.py
=============
Central place for all Qt stylesheets and color constants.
Import STYLESHEET into QApplication.setStyleSheet() once at startup.
"""

# ── Colour palette ───────────────────────────────────────────────────────────
PRIMARY      = "#1a3c5e"
PRIMARY_DARK = "#12293f"
ACCENT       = "#2e86c1"
ACCENT_HOVER = "#1a6fa0"
SUCCESS      = "#27ae60"
WARNING      = "#f39c12"
DANGER       = "#c0392b"
LIGHT_BG     = "#f0f4f8"
CARD_BG      = "#ffffff"
BORDER       = "#cdd5dc"
TEXT_PRIMARY = "#1a1a2e"
TEXT_MUTED   = "#6c757d"

# ── Main stylesheet ──────────────────────────────────────────────────────────
STYLESHEET = f"""
/* ── Global ──────────────────────────────────────── */
QMainWindow, QDialog {{
    background-color: {LIGHT_BG};
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}}

QWidget {{
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}

/* ── Tab Widget ────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {CARD_BG};
    border-radius: 6px;
    top: -1px;
}}

QTabBar::tab {{
    background: #dde6ef;
    color: {TEXT_PRIMARY};
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    font-weight: 500;
    min-width: 100px;
}}

QTabBar::tab:selected {{
    background: {PRIMARY};
    color: white;
    font-weight: 600;
}}

QTabBar::tab:hover:!selected {{
    background: {ACCENT};
    color: white;
}}

/* ── Buttons ───────────────────────────────────────── */
QPushButton {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 5px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
}}

QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton:pressed {{
    background-color: {PRIMARY_DARK};
}}

QPushButton:disabled {{
    background-color: #adb5bd;
    color: #dee2e6;
}}

QPushButton#btn_danger {{
    background-color: {DANGER};
}}
QPushButton#btn_danger:hover {{
    background-color: #a93226;
}}

QPushButton#btn_success {{
    background-color: {SUCCESS};
}}
QPushButton#btn_success:hover {{
    background-color: #1e8449;
}}

QPushButton#btn_warning {{
    background-color: {WARNING};
}}
QPushButton#btn_warning:hover {{
    background-color: #d68910;
}}

QPushButton#btn_secondary {{
    background-color: #6c757d;
}}
QPushButton#btn_secondary:hover {{
    background-color: #5a6268;
}}

/* ── Input Fields ─────────────────────────────────── */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: white;
    border: 1.5px solid {BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
    outline: none;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {ACCENT};
    margin-right: 6px;
}}

/* ── Table Widget ─────────────────────────────────── */
QTableWidget {{
    background-color: white;
    alternate-background-color: {LIGHT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
    selection-color: white;
}}

QTableWidget::item {{
    padding: 6px 8px;
}}

QHeaderView::section {{
    background-color: {PRIMARY};
    color: white;
    font-weight: 600;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid {PRIMARY_DARK};
    font-size: 12px;
}}

QHeaderView::section:hover {{
    background-color: {ACCENT};
}}

/* ── Group Box ────────────────────────────────────── */
QGroupBox {{
    font-weight: 600;
    font-size: 13px;
    border: 1.5px solid {BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    background-color: {CARD_BG};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: -2px;
    padding: 0 6px;
    color: {PRIMARY};
    background-color: {CARD_BG};
}}

/* ── Labels ───────────────────────────────────────── */
QLabel#label_title {{
    font-size: 20px;
    font-weight: 700;
    color: {PRIMARY};
}}

QLabel#label_subtitle {{
    font-size: 13px;
    color: {TEXT_MUTED};
}}

QLabel#stat_value {{
    font-size: 28px;
    font-weight: 700;
    color: {PRIMARY};
}}

QLabel#stat_label {{
    font-size: 12px;
    color: {TEXT_MUTED};
    font-weight: 500;
}}

/* ── Status Bar ───────────────────────────────────── */
QStatusBar {{
    background-color: {PRIMARY};
    color: white;
    font-size: 12px;
    padding: 3px 8px;
}}

/* ── Scroll Bars ─────────────────────────────────── */
QScrollBar:vertical {{
    width: 8px;
    background: {LIGHT_BG};
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}

/* ── Message Box ──────────────────────────────────── */
QMessageBox {{
    background-color: white;
}}

/* ── Dialog ───────────────────────────────────────── */
QDialog {{
    background-color: {LIGHT_BG};
}}
"""
