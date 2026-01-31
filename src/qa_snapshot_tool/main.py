import sys
from PySide6.QtWidgets import QApplication
from gui import MainWindow
from theme import Theme

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QUANTUM Inspector")
    app.setStyleSheet(Theme.get_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()