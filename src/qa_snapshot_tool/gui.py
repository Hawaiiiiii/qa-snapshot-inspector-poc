import os
import json
from typing import Dict, List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QFileDialog,
    QTextEdit,
    QSplitter,
    QGroupBox,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtGui import QPixmap, QPen, QBrush
from PySide6.QtCore import Qt, QRectF, QPointF

from uix_parser import UixParser, UiNode
from locator_suggester import LocatorSuggester
from adb_capture import AdbCapture


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._zoom = 0

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            factor = 1.15
            self._zoom += 1
        else:
            factor = 1 / 1.15
            self._zoom -= 1
        self.scale(factor, factor)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QA Snapshot Inspector & Locator Assistant")
        self.resize(1500, 900)

        # State
        self.current_node_map: Dict[int, UiNode] = {}
        self.current_snapshot_path = ""
        self.snapshots_root = ""
        self.pixmap_item = None
        self.rect_item = None
        self.locator_cache: List[Dict[str, str]] = []

        self.setup_ui()
        self.refresh_devices()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # --- LEFT PANEL: BROWSER & DEVICES ---
        left_layout = QVBoxLayout()
        left_panel = QWidget()
        left_panel.setLayout(left_layout)
        left_panel.setFixedWidth(320)

        # Device Section
        dev_group = QGroupBox("Device (Optional ADB Mode)")
        dev_layout = QVBoxLayout()
        self.device_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh Devices")
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.capture_btn = QPushButton("Capture Snapshot Now")
        self.capture_btn.setStyleSheet("background-color: #d32f2f; font-weight: bold;")
        self.capture_btn.clicked.connect(self.capture_new_snapshot)
        self.device_status = QLabel("ADB status: unknown")
        self.device_status.setWordWrap(True)

        dev_layout.addWidget(self.device_combo)
        dev_layout.addWidget(self.refresh_btn)
        dev_layout.addWidget(self.capture_btn)
        dev_layout.addWidget(self.device_status)
        dev_group.setLayout(dev_layout)

        # Snapshot Browser
        browser_group = QGroupBox("Offline Snapshots")
        browser_layout = QVBoxLayout()
        self.open_folder_btn = QPushButton("Open Snapshot Folder")
        self.open_folder_btn.clicked.connect(self.open_snapshot_folder)

        self.snapshot_list = QTreeWidget()
        self.snapshot_list.setColumnCount(5)
        self.snapshot_list.setHeaderLabels(["Snapshot", "screenshot", "dump.uix", "meta.json", "logcat"])
        self.snapshot_list.itemClicked.connect(self.on_snapshot_clicked)

        self.snapshot_warning = QLabel("")
        self.snapshot_warning.setWordWrap(True)

        browser_layout.addWidget(self.open_folder_btn)
        browser_layout.addWidget(self.snapshot_list)
        browser_layout.addWidget(self.snapshot_warning)
        browser_group.setLayout(browser_layout)

        left_layout.addWidget(dev_group)
        left_layout.addWidget(browser_group)

        # --- CENTER PANEL: VIEWER ---
        center_panel = QGroupBox("UI Viewer")
        center_layout = QVBoxLayout()

        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(self.scene)

        center_layout.addWidget(self.view)
        center_panel.setLayout(center_layout)

        # --- RIGHT PANEL: INSPECTOR ---
        right_splitter = QSplitter(Qt.Vertical)

        # Tree Hierarchy
        self.hierarchy_tree = QTreeWidget()
        self.hierarchy_tree.setHeaderLabel("UI Hierarchy (.uix)")
        self.hierarchy_tree.itemClicked.connect(self.on_hierarchy_item_clicked)
        right_splitter.addWidget(self.hierarchy_tree)

        # Details Panel
        details_group = QGroupBox("Node Details")
        details_layout = QVBoxLayout()
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.details_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        details_layout.addWidget(self.details_table)
        details_group.setLayout(details_layout)
        right_splitter.addWidget(details_group)

        # Locator Suggestions
        locator_group = QGroupBox("Generate Locators")
        loc_layout = QVBoxLayout()
        self.locator_list = QListWidget()
        self.locator_preview = QTextEdit()
        self.locator_preview.setReadOnly(True)
        self.locator_list.currentRowChanged.connect(self.on_locator_selected)

        loc_btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.clicked.connect(self.copy_locator_to_clipboard)
        self.save_btn = QPushButton("Save locator_snippets.txt")
        self.save_btn.clicked.connect(self.save_locator_snippets)
        loc_btn_layout.addWidget(self.copy_btn)
        loc_btn_layout.addWidget(self.save_btn)

        loc_layout.addWidget(self.locator_list)
        loc_layout.addWidget(self.locator_preview)
        loc_layout.addLayout(loc_btn_layout)
        locator_group.setLayout(loc_layout)
        right_splitter.addWidget(locator_group)

        # Combine Layouts
        splitter_main = QSplitter(Qt.Horizontal)
        splitter_main.addWidget(left_panel)
        splitter_main.addWidget(center_panel)
        splitter_main.addWidget(right_splitter)
        splitter_main.setStretchFactor(1, 2)
        splitter_main.setStretchFactor(2, 2)

        main_layout.addWidget(splitter_main)

    # --- LOGIC: ADB ---
    def refresh_devices(self):
        self.device_combo.clear()
        devices = AdbCapture.get_devices()
        self.device_combo.addItems(devices)
        if devices and "Error" in devices[0]:
            self.device_status.setText("ADB not found. Offline mode only.")
        else:
            self.device_status.setText(f"{len(devices)} device(s) detected")

    def capture_new_snapshot(self):
        device = self.device_combo.currentText()
        if not device or "Error" in device or "offline" in device:
            QMessageBox.warning(self, "Error", "Select a valid online device first.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Save Location")
        if folder:
            import datetime

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            snap_path = os.path.join(folder, f"snapshot_{timestamp}")

            self.capture_btn.setText("Capturing... wait...")
            self.capture_btn.setEnabled(False)
            self.repaint()

            try:
                success, path = AdbCapture.capture_snapshot(device, snap_path)
                if success:
                    self.load_snapshot(path)
                    self.populate_snapshot_list(folder)
            except Exception as e:
                QMessageBox.critical(self, "Capture Failed", str(e))
            finally:
                self.capture_btn.setText("Capture Snapshot Now")
                self.capture_btn.setEnabled(True)

    # --- LOGIC: OFFLINE LOADING ---
    def open_snapshot_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Snapshot Folder or Parent")
        if not folder:
            return

        if self._is_snapshot_folder(folder):
            self.snapshots_root = os.path.dirname(folder)
            self.populate_snapshot_list(self.snapshots_root)
            self.load_snapshot(folder)
        else:
            self.snapshots_root = folder
            self.populate_snapshot_list(folder)
            latest = self._get_latest_snapshot(folder)
            if latest:
                self.load_snapshot(latest)

    def populate_snapshot_list(self, parent_folder: str):
        self.snapshot_list.clear()
        if not os.path.isdir(parent_folder):
            return

        folders = [
            os.path.join(parent_folder, d)
            for d in os.listdir(parent_folder)
            if os.path.isdir(os.path.join(parent_folder, d))
        ]
        folders.sort(key=lambda p: os.path.getmtime(p), reverse=True)

        for folder in folders:
            base = os.path.basename(folder)
            status = self._snapshot_status(folder)
            item = QTreeWidgetItem([
                base,
                status["screenshot"],
                status["dump"],
                status["meta"],
                status["logcat"],
            ])
            if status["missing"]:
                item.setForeground(0, QBrush(Qt.yellow))
            for idx, key in enumerate(["screenshot", "dump", "meta", "logcat"], start=1):
                if status[key] == "Missing":
                    item.setForeground(idx, QBrush(Qt.red))
                else:
                    item.setForeground(idx, QBrush(Qt.green))
            self.snapshot_list.addTopLevelItem(item)
            item.setData(0, Qt.UserRole, folder)

    def on_snapshot_clicked(self, item, col):
        path = item.data(0, Qt.UserRole)
        if path:
            self.load_snapshot(path)

    def load_snapshot(self, path: str):
        self.current_snapshot_path = path
        self.setWindowTitle(f"Inspector - {os.path.basename(path)}")

        warnings = []

        # 1. Load Image
        img_path = os.path.join(path, "screenshot.png")
        self.scene.clear()
        self.pixmap_item = None
        self.rect_item = None
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            self.pixmap_item = self.scene.addPixmap(pixmap)
            self.rect_item = QGraphicsRectItem()
            self.rect_item.setPen(QPen(Qt.red, 2))
            self.rect_item.setZValue(1)
            self.scene.addItem(self.rect_item)
            self.rect_item.hide()
        else:
            warnings.append("screenshot.png missing")

        # 2. Load XML
        xml_path = os.path.join(path, "dump.uix")
        self.hierarchy_tree.clear()
        self.current_node_map = {}
        if os.path.exists(xml_path):
            root_node = UixParser.parse(xml_path)
            if root_node:
                self.populate_tree(root_node, self.hierarchy_tree)
        else:
            warnings.append("dump.uix missing")

        # 3. Load Meta (Optional)
        meta_path = os.path.join(path, "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.snapshot_warning.setText(f"Meta: activity {data.get('focus', '')}")
            except Exception:
                warnings.append("meta.json malformed")
        else:
            warnings.append("meta.json missing")

        # 4. Logcat (Optional)
        log_path = os.path.join(path, "logcat.txt")
        if not os.path.exists(log_path):
            warnings.append("logcat.txt missing")

        if warnings:
            self.snapshot_warning.setText("Warnings: " + ", ".join(warnings))
        else:
            self.snapshot_warning.setText("Snapshot loaded successfully.")

    def populate_tree(self, node: UiNode, parent_widget):
        display_text = node.class_name or "<unknown>"
        if node.resource_id:
            display_text += f" ({node.resource_id.split('/')[-1]})"
        elif node.text:
            display_text += f" [\"{node.text}\"]"

        item = QTreeWidgetItem(parent_widget)
        item.setText(0, display_text)
        self.current_node_map[id(item)] = node

        for child in node.children:
            self.populate_tree(child, item)

    # --- LOGIC: INTERACTION ---
    def on_hierarchy_item_clicked(self, item, col):
        node = self.current_node_map.get(id(item))
        if not node:
            return

        # 1. Draw Rect
        if self.rect_item:
            x, y, w, h = node.rect
            self.rect_item.setRect(QRectF(x, y, w, h))
            self.rect_item.show()
            self.view.centerOn(QPointF(x + w / 2, y + h / 2))

        # 2. Update Properties
        self.details_table.setRowCount(0)
        props = [
            ("Text", node.text),
            ("Resource-ID", node.resource_id),
            ("Class", node.class_name),
            ("Package", node.package),
            ("Content-Desc", node.content_desc),
            ("Bounds", node.bounds_raw),
            ("Clickable", str(node.clickable)),
            ("Checked", str(node.checked)),
            ("Enabled", str(node.enabled)),
            ("Focused", str(node.focused)),
        ]
        for i, (k, v) in enumerate(props):
            self.details_table.insertRow(i)
            self.details_table.setItem(i, 0, QTableWidgetItem(k))
            self.details_table.setItem(i, 1, QTableWidgetItem(v))

        # 3. Generate Locators
        self.locator_cache = LocatorSuggester.generate_locators(node)
        self.locator_list.clear()
        for entry in self.locator_cache:
            self.locator_list.addItem(QListWidgetItem(entry["type"]))
        if self.locator_cache:
            self.locator_list.setCurrentRow(0)

    def on_locator_selected(self, index: int):
        if index < 0 or index >= len(self.locator_cache):
            self.locator_preview.setText("")
            return
        entry = self.locator_cache[index]
        self.locator_preview.setText(entry.get("value", ""))

    def copy_locator_to_clipboard(self):
        text = self.locator_preview.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "No locator", "Select a node to generate locators.")
            return
        self.locator_preview.selectAll()
        self.locator_preview.copy()

    def save_locator_snippets(self):
        if not self.current_snapshot_path:
            QMessageBox.information(self, "No snapshot", "Load a snapshot first.")
            return
        if not self.locator_cache:
            QMessageBox.information(self, "No locators", "Select a node to generate locators.")
            return

        out_path = os.path.join(self.current_snapshot_path, "locator_snippets.txt")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                for entry in self.locator_cache:
                    f.write(f"{entry['type']}\n")
                    f.write(f"{entry['value']}\n\n")
            QMessageBox.information(self, "Saved", f"Saved to {out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

    def _snapshot_status(self, folder: str) -> Dict[str, str]:
        screenshot = os.path.exists(os.path.join(folder, "screenshot.png"))
        dump = os.path.exists(os.path.join(folder, "dump.uix"))
        meta = os.path.exists(os.path.join(folder, "meta.json"))
        logcat = os.path.exists(os.path.join(folder, "logcat.txt"))
        missing = not (screenshot and dump)

        return {
            "screenshot": "OK" if screenshot else "Missing",
            "dump": "OK" if dump else "Missing",
            "meta": "OK" if meta else "Missing",
            "logcat": "OK" if logcat else "Missing",
            "missing": missing,
        }

    def _is_snapshot_folder(self, folder: str) -> bool:
        return any(
            os.path.exists(os.path.join(folder, name))
            for name in ["screenshot.png", "dump.uix", "meta.json", "logcat.txt"]
        )

    def _get_latest_snapshot(self, parent: str) -> str:
        folders = [
            os.path.join(parent, d)
            for d in os.listdir(parent)
            if os.path.isdir(os.path.join(parent, d))
        ]
        if not folders:
            return ""
        return sorted(folders, key=lambda p: os.path.getmtime(p), reverse=True)[0]