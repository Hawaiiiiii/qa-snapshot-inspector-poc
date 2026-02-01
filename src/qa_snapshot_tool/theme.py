"""
Application Theme Module.

Defines the color palette, fonts, and QSS style sheets used throughout the application.
Designed for a modern "Dark Mode" aesthetic similar to VS Code or JetBrains IDEs.
"""

from PySide6.QtGui import QColor

class Theme:
    """
    Static container for UI theme constants and stylesheet generation.
    """
    
    # Colors
    BMW_BLUE: str = "#1c69d4"
    BMW_BLUE_GRADIENT: str = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d7dec, stop:1 #1c69d4)"
    
    BG_DARK: str = "#1e1e1e"
    BG_PANEL: str = "#252526"
    BG_HEADER: str = "#2d2d30"
    BORDER: str = "#3e3e42"
    
    TEXT_WHITE: str = "#f0f0f0"
    TEXT_GRAY: str = "#cccccc"
    
    ACCENT_RED: str = "#d32f2f"
    ACCENT_RED_GRADIENT: str = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff5252, stop:1 #d32f2f)"
    
    ACCENT_GREEN: str = "#388e3c"
    ACCENT_YELLOW: str = "#fbc02d"

    SELECTION_OVERLAY: str = "rgba(255, 0, 0, 80)"
    HOVER_OVERLAY: str = "rgba(255, 255, 255, 30)"

    @staticmethod
    def get_stylesheet() -> str:
        """
        Returns the global QSS stylesheet for the application.
        """
        return f"""
        QMainWindow {{
            background-color: {Theme.BG_DARK};
        }}
        
        QWidget {{
            color: {Theme.TEXT_WHITE};
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
        }}
        
        /* Docks */
        QDockWidget {{
            titlebar-close-icon: url(close.png);
            titlebar-normal-icon: url(float.png);
        }}
        
        QDockWidget::title {{
            background: {Theme.BG_HEADER};
            padding-left: 5px;
            padding-top: 4px;
            padding-bottom: 4px; 
            border-bottom: 1px solid {Theme.BORDER};
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: {Theme.BG_DARK};
            width: 10px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #424242;
            min-height: 20px;
            border-radius: 5px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
        
        /* Lists & Trees */
        QTreeWidget, QListWidget {{
            background-color: {Theme.BG_PANEL};
            border: 1px solid {Theme.BORDER};
            outline: none;
        }}
        QTreeWidget::item, QListWidget::item {{
            padding: 4px;
        }}
        QTreeWidget::item:selected, QListWidget::item:selected {{
            background-color: #37373d;
            color: white;
        }}
        QTreeWidget::item:hover, QListWidget::item:hover {{
            background-color: #2a2d2e;
        }}

        /* Buttons */
        QPushButton {{
            background-color: {Theme.BG_HEADER};
            border: 1px solid {Theme.BORDER};
            padding: 6px 12px;
            border-radius: 3px;
        }}
        QPushButton:hover {{
            background-color: #3e3e42;
        }}
        QPushButton:pressed {{
            background-color: #0e639c; /* VSCode Blue */
            border-color: #0e639c;
            color: white;
        }}
        
        /* Header specific buttons */
        QPushButton#primaryBtn {{
            background: {Theme.BMW_BLUE_GRADIENT};
            border: 1px solid #1055b3;
            font-weight: bold;
        }}
        QPushButton#primaryBtn:hover {{
            background: #2d7dec;
        }}
        
        QPushButton#dangerBtn {{
            background: {Theme.ACCENT_RED_GRADIENT};
            border: 1px solid #b71c1c;
            font-weight: bold;
        }}

        /* Inputs */
        QLineEdit, QTextEdit {{
            background-color: #3c3c3c;
            border: 1px solid {Theme.BORDER};
            padding: 4px;
            color: {Theme.TEXT_WHITE};
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {Theme.BMW_BLUE};
        }}
        
        /* Labels */
        QLabel#h1 {{
            font-size: 16px;
            font-weight: bold;
            color: {Theme.TEXT_WHITE};
            margin-bottom: 8px;
        }}
        QLabel#h2 {{
            font-size: 12px;
            font-weight: bold;
            color: {Theme.TEXT_GRAY};
            margin-top: 10px;
            margin-bottom: 4px;
        }}
        QLabel#infoLabel {{
            color: {Theme.TEXT_GRAY};
        }}
        """
