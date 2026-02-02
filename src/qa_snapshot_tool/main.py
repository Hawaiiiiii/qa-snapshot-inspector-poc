"""
Application Entry Point.

This module initializes the PySide6 application, applies the global theme,
and launches the main window. It serves as the bootstrap for the desktop GUI.
"""

import os
import sys
from pathlib import Path

os.environ["QT_LOGGING_RULES"] = "qt.multimedia.*=false;qt.multimedia.ffmpeg.*=false"

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtCore import QLoggingCategory
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
    QLoggingCategory.setFilterRules("qt.multimedia.*=false\nqt.multimedia.ffmpeg.*=false")
    app = QApplication(sys.argv)
    app.setApplicationName("QUANTUM Inspector")

    fonts_dir = Path(__file__).resolve().parents[2] / "assets" / "fonts"
    if fonts_dir.exists():
        loaded_families = []
        for font_path in list(fonts_dir.rglob("*.ttf")) + list(fonts_dir.rglob("*.otf")):
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id != -1:
                loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))

    font_family = "BMW Type Next"
    if "loaded_families" in locals() and loaded_families:
        font_family = loaded_families[0]
    if font_family not in QFontDatabase.families():
        font_family = "Segoe UI"

    Theme.FONT_FAMILY = font_family

    base_font = QFont(font_family)
    base_font.setPointSize(10)
    app.setFont(base_font)
    app.setStyleSheet(Theme.get_stylesheet())

    window = MainWindow()
    icon_path = Path(__file__).resolve().parents[2] / "assets" / "icons" / "quantum.svg"
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    window.log_sys(f"Font family active: {font_family}")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
