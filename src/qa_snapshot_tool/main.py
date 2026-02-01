"""
Application Entry Point.

This module initializes the PySide6 application, applies the global theme,
and launches the main window. It serves as the bootstrap for the desktop GUI.
"""

import sys
from PySide6.QtWidgets import QApplication
from .gui import MainWindow
from .theme import Theme

def main() -> None:
    """
    Main execution function.
    Initializes the Qt Application context and event loop.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("QUANTUM Inspector")
    app.setStyleSheet(Theme.get_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
