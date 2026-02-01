"""
Application Entry Point.

This module initializes the PySide6 application, applies the global theme,
and launches the main window. It serves as the bootstrap for the desktop GUI.
"""

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qa_snapshot_tool.gui import MainWindow
from qa_snapshot_tool.theme import Theme

def main() -> None:
    """
    Main execution function.
    Initializes the Qt Application context and event loop.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("QUANTUM Inspector")

    fonts_dir = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    if fonts_dir.exists():
        for font_path in fonts_dir.glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(font_path))

    font_family = "BMW Type Next"
    if font_family not in QFontDatabase.families():
        font_family = "Segoe UI"

    base_font = QFont(font_family)
    base_font.setPointSize(10)
    app.setFont(base_font)
    app.setStyleSheet(Theme.get_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
