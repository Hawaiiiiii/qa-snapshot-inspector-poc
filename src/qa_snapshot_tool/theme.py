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

    FONT_FAMILY: str = "BMW Type Next"
    FONT_FALLBACK: str = "Segoe UI"
    
    # Colors
    BMW_BLUE: str = "#1c69d4"
    BMW_BLUE_HIGHLIGHT: str = "#2d7dec"
    BMW_BLUE_GRADIENT: str = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f4aa0, stop:0.55 #1c69d4, stop:1 #2d7dec)"

    PARADOX_PINK: str = "#ff2d95"
    PARADOX_PURPLE: str = "#7a2cff"
    PARADOX_GRADIENT: str = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff2d95, stop:0.55 #b030ff, stop:1 #7a2cff)"
    
    BG_DARK: str = "#101317"
    BG_PANEL: str = "#161a20"
    BG_HEADER: str = "#1a1f27"
    BG_ELEVATED: str = "#1f2530"
    BORDER: str = "#2b3442"
    
    TEXT_WHITE: str = "#f0f0f0"
    TEXT_GRAY: str = "#cccccc"
    
    ACCENT_RED: str = "#d32f2f"
    ACCENT_RED_GRADIENT: str = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff5252, stop:1 #d32f2f)"
    
    ACCENT_GREEN: str = "#388e3c"
    ACCENT_YELLOW: str = "#fbc02d"

    SELECTION_OVERLAY: str = "rgba(255, 0, 0, 80)"
    HOVER_OVERLAY: str = "rgba(255, 255, 255, 30)"

    @staticmethod
    def get_stylesheet(ambient_overlay: str = "", use_translucent: bool = False) -> str:
        """
        Returns the global QSS stylesheet for the application.
        """
        panel_bg = "rgba(22, 26, 32, 200)" if use_translucent else Theme.BG_PANEL
        header_bg = "rgba(26, 31, 39, 200)" if use_translucent else Theme.BG_HEADER
        dark_bg = "rgba(16, 19, 23, 220)" if use_translucent else Theme.BG_DARK
        elevated_bg = "rgba(31, 37, 48, 210)" if use_translucent else Theme.BG_ELEVATED
        return f"""
        QMainWindow {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0b0f14, stop:0.6 #121722, stop:1 #10131a);
            {ambient_overlay}
        }}
        
        QWidget {{
            color: {Theme.TEXT_WHITE};
            font-family: '{Theme.FONT_FAMILY}', '{Theme.FONT_FALLBACK}', sans-serif;
            font-size: 10pt;
        }}

        QToolBar {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10151d, stop:0.6 #151b26, stop:1 #111722);
            border-bottom: 1px solid {Theme.BORDER};
            spacing: 12px;
        }}
        
        /* Docks */
        QDockWidget {{
            titlebar-close-icon: url(close.png);
            titlebar-normal-icon: url(float.png);
        }}
        
        QDockWidget::title {{
            background: {header_bg};
            padding-left: 5px;
            padding-top: 4px;
            padding-bottom: 4px; 
            border-bottom: 1px solid {Theme.BORDER};
        }}

        QDockWidget::title::text {{
            color: {Theme.TEXT_GRAY};
            font-weight: 600;
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
            background-color: {panel_bg};
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
            background-color: {elevated_bg};
            border: 1px solid {Theme.BORDER};
            padding: 7px 12px;
            border-radius: 6px;
        }}
        QPushButton:hover {{
            background-color: #2a3342;
        }}
        QPushButton:pressed {{
            background-color: {Theme.BMW_BLUE};
            border-color: {Theme.BMW_BLUE};
            color: white;
        }}
        
        /* Header specific buttons */
        QPushButton[class="primary"] {{
            background: {Theme.BMW_BLUE_GRADIENT};
            border: 1px solid #1055b3;
            font-weight: 600;
        }}
        QPushButton[class="primary"]:hover {{
            background: {Theme.BMW_BLUE_HIGHLIGHT};
        }}
        QPushButton[class="accent"] {{
            background: {Theme.PARADOX_GRADIENT};
            border: 1px solid #6a1fd4;
            font-weight: 600;
        }}
        
        QPushButton[class="danger"] {{
            background: {Theme.ACCENT_RED_GRADIENT};
            border: 1px solid #b71c1c;
            font-weight: 600;
        }}

        /* Inputs */
        QLineEdit, QTextEdit {{
            background-color: {dark_bg};
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

        QGroupBox {{
            border: 1px solid {Theme.BORDER};
            margin-top: 10px;
            border-radius: 6px;
            background: {panel_bg};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px 0 4px;
            color: {Theme.TEXT_GRAY};
        }}

        QTabWidget::pane {{
            border: 1px solid {Theme.BORDER};
            background: {panel_bg};
        }}
        QTabBar::tab {{
            background: {header_bg};
            padding: 6px 12px;
            margin-right: 2px;
            border: 1px solid {Theme.BORDER};
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }}
        QTabBar::tab:selected {{
            background: {elevated_bg};
            border-bottom-color: {elevated_bg};
        }}

        QHeaderView::section {{
            background: {header_bg};
            border: 1px solid {Theme.BORDER};
            padding: 4px;
        }}
        """
