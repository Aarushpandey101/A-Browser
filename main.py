# super_browser/main.py

import sys
from PyQt6.QtWidgets import QApplication
from browser_window import BrowserWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = BrowserWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()