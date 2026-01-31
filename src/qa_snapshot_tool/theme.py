from PySide6.QtGui import QColor

class Theme:
    # Colors
    BMW_BLUE = "#1c69d4"
    BMW_BLUE_GRADIENT = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d7dec, stop:1 #1c69d4)"
    
    BG_DARK = "#1e1e1e"
    BG_PANEL = "#252526"
    BG_HEADER = "#2d2d30"
    BORDER = "#3e3e42"
    
    TEXT_WHITE = "#f0f0f0"
    TEXT_GRAY = "#cccccc"
    
    ACCENT_RED = "#d32f2f"
    ACCENT_RED_GRADIENT = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff5252, stop:1 #d32f2f)"
    
    ACCENT_GREEN = "#388e3c"
    ACCENT_YELLOW = "#fbc02d"

    FONT_FAMILY = "Segoe UI, Roboto, Helvetica, Arial, sans-serif"

    @staticmethod
    def get_stylesheet():
        return f"""
        QMainWindow {{ background-color: {Theme.BG_DARK}; color: {Theme.TEXT_WHITE}; }}
        QWidget {{ font-family: "{Theme.FONT_FAMILY}"; font-size: 9pt; color: {Theme.TEXT_WHITE}; }}
        
        QToolTip {{ 
            background-color: {Theme.BG_HEADER}; 
            color: {Theme.TEXT_WHITE}; 
            border: 1px solid {Theme.BMW_BLUE}; 
            padding: 5px;
        }}

        /* Dock & Panels */
        QDockWidget::title {{ background: {Theme.BG_HEADER}; padding: 6px; border-bottom: 2px solid {Theme.BORDER}; }}
        QGroupBox {{ border: 1px solid {Theme.BORDER}; margin-top: 1.5em; background-color: {Theme.BG_PANEL}; border-radius: 4px; }}
        QGroupBox::title {{ subcontrol-origin: margin; padding: 0 5px; color: {Theme.BMW_BLUE}; font-weight: bold; }}

        /* Buttons with Gradients */
        QPushButton {{
            background-color: {Theme.BG_HEADER};
            border: 1px solid {Theme.BORDER};
            padding: 6px 12px;
            border-radius: 3px;
        }}
        QPushButton:hover {{ background-color: {Theme.BORDER}; }}
        QPushButton:pressed {{ background-color: {Theme.BG_DARK}; }}
        
        QPushButton[class="primary"] {{
            background: {Theme.BMW_BLUE_GRADIENT};
            border: 1px solid {Theme.BMW_BLUE};
            font-weight: bold;
        }}
        QPushButton[class="primary"]:hover {{ background-color: {Theme.BMW_BLUE}; }}
        
        QPushButton[class="danger"] {{
            background: {Theme.ACCENT_RED_GRADIENT};
            border: 1px solid {Theme.ACCENT_RED};
            font-weight: bold;
        }}

        /* Input Fields */
        QComboBox, QLineEdit, QTextEdit, QTableWidget, QTreeWidget {{
            background-color: #2d2d30;
            border: 1px solid {Theme.BORDER};
            color: {Theme.TEXT_WHITE};
            selection-background-color: {Theme.BMW_BLUE};
        }}
        
        QHeaderView::section {{
            background-color: {Theme.BG_HEADER};
            padding: 4px;
            border: none;
            border-right: 1px solid {Theme.BORDER};
            border-bottom: 1px solid {Theme.BORDER};
        }}
        
        QTabWidget::pane {{ border: 1px solid {Theme.BORDER}; }}
        QTabBar::tab {{
            background: {Theme.BG_HEADER};
            padding: 8px 16px;
            border: 1px solid {Theme.BORDER};
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background: {Theme.BG_PANEL};
            border-bottom: 2px solid {Theme.BMW_BLUE};
            color: {Theme.BMW_BLUE};
            font-weight: bold;
        }}
        
        QStatusBar {{ background: {Theme.BG_HEADER}; color: {Theme.TEXT_GRAY}; }}
        """