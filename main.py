"""
main.py
=======
Application entry point.

Run with:
    python main.py

Requirements:
    pip install PyQt5 reportlab openpyxl Pillow
"""

import sys
import os

# ── Ensure project root is on the Python path ─────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt5.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtGui     import QFont, QPixmap, QColor

from database.connection import DatabaseManager
from ui.main_window      import MainWindow
from ui.styles           import STYLESHEET


def create_splash(app: QApplication) -> QSplashScreen:
    """Simple programmatic splash screen."""
    pix = QPixmap(460, 220)
    pix.fill(QColor("#1a3c5e"))

    from PyQt5.QtGui import QPainter, QPen
    painter = QPainter(pix)
    painter.setPen(QPen(QColor("white")))

    font_big = QFont("Segoe UI", 26, QFont.Bold)
    painter.setFont(font_big)
    painter.drawText(pix.rect(), Qt.AlignCenter | Qt.AlignTop,
                     "\n\n🖨️  PrintBill Pro")

    font_sm = QFont("Segoe UI", 11)
    painter.setFont(font_sm)
    painter.setPen(QPen(QColor("#adb5bd")))
    painter.drawText(pix.rect(), Qt.AlignCenter | Qt.AlignBottom,
                     "Initialising...  \n\n")
    painter.end()

    splash = QSplashScreen(pix)
    splash.setWindowFlag(Qt.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()
    return splash


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PrintBill Pro")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    # Splash
    splash = create_splash(app)

    # Initialise database
    db = DatabaseManager()
    db.initialize()

    # Build main window
    window = MainWindow(db)

    # Close splash and show window after a brief delay
    def launch():
        splash.finish(window)
        window.show()

    QTimer.singleShot(1200, launch)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
