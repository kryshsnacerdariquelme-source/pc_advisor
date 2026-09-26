import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "Backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from Desktop.main_window import MainWindow, apply_style


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PC Advisor")
    app.setOrganizationName("PC Advisor")
    apply_style(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
