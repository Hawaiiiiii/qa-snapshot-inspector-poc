"""
Main GUI Module.

This module implements the MainWindow class, which is the central hub of the desktop application.
It orchestrates the various docks, views, and controllers, including:
- Screenshot visualization (QGraphicsView)
- Hierarchy tree (QTreeWidget)
- Node property inspection
- Device control and snapshot capture
"""
import os
import glob
import time
import json
import math
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QFileDialog, QTextEdit,
    QGroupBox, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QToolBar, QTabWidget, QStatusBar, QFrame, QDockWidget, QApplication, QLineEdit, QCheckBox
)
from PySide6.QtGui import QPixmap, QPen, QBrush, QImage, QColor, QAction, QPainter, QCursor
from PySide6.QtCore import Qt, QRectF, Signal, QTimer

from qa_snapshot_tool.uix_parser import UixParser
from qa_snapshot_tool.locator_suggester import LocatorSuggester
from qa_snapshot_tool.adb_manager import AdbManager
from qa_snapshot_tool.live_mirror import VideoThread, HierarchyThread, LogcatThread, FocusMonitorThread
from qa_snapshot_tool.theme import Theme

class SmartGraphicsView(QGraphicsView):
    mouse_moved = Signal(int, int)
    input_tap = Signal(int, int)
    input_swipe = Signal(int, int, int, int)
    view_resized = Signal()

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFrameShape(QFrame.NoFrame)
        self.setBackgroundBrush(QBrush(QColor(Theme.BG_DARK)))
        
        self.click_enabled = True
        self.control_enabled = False
        self._drag_start = None
        self.crosshair_pos = None # Scene coordinates

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0: self.scale(1.1, 1.1)
            else: self.scale(0.9, 0.9)
            event.accept()
        elif self.control_enabled:
            # Simulate scroll
            delta = event.angleDelta().y()
            self.input_swipe.emit(500, 800, 500, 800 + int(delta))
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = self.mapToScene(event.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_start:
            end = self.mapToScene(event.pos())
            dx = end.x() - self._drag_start.x()
            dy = end.y() - self._drag_start.y()
            dist = (dx**2 + dy**2)**0.5
            
            if self.control_enabled:
                if dist > 20: 
                    self.input_swipe.emit(int(self._drag_start.x()), int(self._drag_start.y()), int(end.x()), int(end.y()))
                else:
                    self.input_tap.emit(int(end.x()), int(end.y()))
            else:
                if dist < 20 and self.click_enabled:
                    self.input_tap.emit(int(end.x()), int(end.y()))
            self._drag_start = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        # Map viewport position to Scene Position for accurate Crosshair
        scene_pos = self.mapToScene(event.pos())
        self.crosshair_pos = scene_pos
        self.mouse_moved.emit(int(scene_pos.x()), int(scene_pos.y()))
        self.viewport().update() # Trigger repaint
        super().mouseMoveEvent(event)

    def drawForeground(self, painter, rect):
        if self.crosshair_pos:
            painter.setPen(QPen(QColor(Theme.ACCENT_YELLOW), 1, Qt.DashLine))
            x = self.crosshair_pos.x()
            y = self.crosshair_pos.y()
            
            # Draw infinite lines across the scene
            scene_rect = self.sceneRect()
            painter.drawLine(x, scene_rect.top(), x, scene_rect.bottom())
            painter.drawLine(scene_rect.left(), y, scene_rect.right(), y)
            
            # Draw coordinates text
            text = f"({int(x)}, {int(y)})"
            painter.setPen(QPen(QColor(Theme.TEXT_WHITE), 1))
            painter.drawText(x + 10, y - 10, text)
            
        super().drawForeground(painter, rect)

    def resizeEvent(self, e): self.view_resized.emit(); super().resizeEvent(e)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QUANTUM Inspector | Paradox Cat Internal")
        self.resize(1600, 1000)
        
        self.current_node_map = {}
        self.node_to_item_map = {}
        self.rect_map = []
        self.active_device = None
        self.root_node = None
        
        # Threads
        self.video_thread = None
        self.xml_thread = None
        self.log_thread = None
        self.focus_thread = None
        
        self.locked_node = False
        self.locked_node_id = None
        self.auto_follow_hover = True
        self.stream_max_size = None
        self.ambient_enabled = True
        self.ambient_phase = 0.0
        self.auto_fit = True
        self.fps_counter = 0
        
        self.setup_ui()
        self.refresh_devices()

        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)

        self.ambient_timer = QTimer()
        self.ambient_timer.timeout.connect(self.update_ambient)
        self.ambient_timer.start(250)

    def setup_ui(self):
        central = QWidget(); central_lay = QVBoxLayout(central); central_lay.setContentsMargins(0,0,0,0)
        
        # Toolbar
        tb = QToolBar()
        self.lbl_fps = QLabel("FPS: 0"); self.lbl_fps.setStyleSheet("color: #7c8aa3; font-weight: 600;")
        self.lbl_coords = QLabel("X: 0, Y: 0"); self.lbl_coords.setStyleSheet("color: #c1c7d2; font-family: monospace;")
        self.lbl_focus = QLabel("Focus: -"); self.lbl_focus.setStyleSheet("color: #7db6ff; font-weight: 600;")
        
        act_fit = QAction("Fit Screen", self); act_fit.triggered.connect(self.enable_fit)
        act_11 = QAction("1:1 Pixel", self); act_11.triggered.connect(self.disable_fit)
        
        tb.addWidget(self.lbl_fps); tb.addWidget(self.lbl_coords); tb.addSeparator(); tb.addWidget(self.lbl_focus)
        tb.addSeparator(); tb.addAction(act_fit); tb.addAction(act_11)
        central_lay.addWidget(tb)
        
        # View
        self.scene = QGraphicsScene()
        self.view = SmartGraphicsView(self.scene)
        self.view.mouse_moved.connect(self.on_mouse_hover)
        self.view.input_tap.connect(self.handle_tap)
        self.view.input_swipe.connect(self.handle_swipe)
        self.view.view_resized.connect(self.handle_resize)
        central_lay.addWidget(self.view)
        
        self.setCentralWidget(central)

        # Docks
        self.setup_control_dock()
        self.setup_tree_dock()
        self.setup_inspector_dock()

        # Overlay Items
        self.rect_item = QGraphicsRectItem()
        self.rect_item.setPen(QPen(QColor(Theme.BMW_BLUE), 3))
        self.rect_item.setZValue(99)
        self.scene.addItem(self.rect_item); self.rect_item.hide()
        self.pixmap_item = None

    def setup_control_dock(self):
        d = QDockWidget("Environment", self); w = QWidget(); l = QVBoxLayout(w)
        
        # Device Selection
        gb_dev = QGroupBox("Target Device"); gl = QVBoxLayout()
        self.combo_dev = QComboBox(); self.combo_dev.currentIndexChanged.connect(self.on_dev_change)
        self.combo_dev.setToolTip("Select a connected device (USB or Wi‑Fi).")

        btn_ref = QPushButton("Refresh List"); btn_ref.clicked.connect(self.refresh_devices)
        btn_ref.setToolTip("Rescan ADB for connected devices.")

        ip_row = QHBoxLayout()
        self.input_ip = QLineEdit(); self.input_ip.setPlaceholderText("IP:port (e.g., 192.168.0.20:5555)")
        self.input_ip.setToolTip("Connect to a device over Wi‑Fi using adb connect.")
        self.btn_connect_ip = QPushButton("Connect IP"); self.btn_connect_ip.setProperty("class", "accent")
        self.btn_connect_ip.clicked.connect(self.connect_ip_device)
        self.btn_connect_ip.setToolTip("Connect to a device by IP address.")
        ip_row.addWidget(self.input_ip); ip_row.addWidget(self.btn_connect_ip)

        hist_row = QHBoxLayout()
        self.combo_history = QComboBox()
        self.combo_history.setToolTip("Recently connected devices and IPs.")
        self.btn_reconnect = QPushButton("Reconnect"); self.btn_reconnect.clicked.connect(self.reconnect_history)
        self.btn_reconnect.setToolTip("Reconnect to the selected recent device.")
        hist_row.addWidget(self.combo_history); hist_row.addWidget(self.btn_reconnect)

        gl.addWidget(self.combo_dev); gl.addWidget(btn_ref)
        gl.addLayout(ip_row)
        gl.addLayout(hist_row)
        gb_dev.setLayout(gl); l.addWidget(gb_dev)
        
        # Live Modes
        gb_live = QGroupBox("Live Mirror"); ll = QVBoxLayout()
        self.btn_live = QPushButton("START LIVE STREAM"); self.btn_live.setProperty("class", "primary")
        self.btn_live.clicked.connect(self.toggle_live)
        self.chk_turbo = QLabel("Optimized"); self.chk_turbo.setStyleSheet("color: #8aa1c1; font-size: 9pt;")
        self.btn_live.setToolTip("Start or stop live mirroring and control input.")

        res_row = QHBoxLayout()
        self.combo_res = QComboBox()
        self.combo_res.addItems(["Native", "1024", "1280", "1600", "1920"])
        self.combo_res.currentIndexChanged.connect(self.on_stream_size_change)
        self.combo_res.setToolTip("Reduce stream resolution for better performance.")
        lbl_res = QLabel("Max Size"); lbl_res.setToolTip("Maximum stream width/height (preserves aspect ratio).")
        res_row.addWidget(lbl_res); res_row.addWidget(self.combo_res)

        ll.addWidget(self.btn_live); ll.addWidget(self.chk_turbo); ll.addLayout(res_row)
        gb_live.setLayout(ll); l.addWidget(gb_live)
        
        # Snapshots
        gb_snap = QGroupBox("Snapshot / Offline"); sl = QVBoxLayout()
        btn_cap = QPushButton("Capture Snapshot"); btn_cap.setProperty("class", "primary"); btn_cap.clicked.connect(self.capture_snapshot)
        btn_cap.setToolTip("Capture screenshot, UI dump, and logcat into a snapshot folder.")
        btn_load = QPushButton("Load Offline Dump..."); btn_load.setProperty("class", "accent"); btn_load.clicked.connect(self.load_snapshot_dialog)
        btn_load.setToolTip("Load an offline dump (dump.uix) from a snapshot folder.")
        sl.addWidget(btn_cap); sl.addWidget(btn_load)
        gb_snap.setLayout(sl); l.addWidget(gb_snap)

        gb_opts = QGroupBox("UX Options"); ol = QVBoxLayout()
        self.chk_auto_follow = QCheckBox("Auto Locate Hover")
        self.chk_auto_follow.setChecked(True)
        self.chk_auto_follow.stateChanged.connect(self.toggle_auto_follow)
        self.chk_auto_follow.setToolTip("Auto-scroll the UI Tree to the element under the cursor.")

        self.chk_ambient = QCheckBox("Ambient Glow")
        self.chk_ambient.setChecked(True)
        self.chk_ambient.stateChanged.connect(self.toggle_ambient)
        self.chk_ambient.setToolTip("Animated gradient for BMW-style ambient feel. Disable for performance.")

        ol.addWidget(self.chk_auto_follow); ol.addWidget(self.chk_ambient)
        gb_opts.setLayout(ol); l.addWidget(gb_opts)
        
        l.addStretch()
        d.setWidget(w); self.addDockWidget(Qt.LeftDockWidgetArea, d)

    def setup_tree_dock(self):
        d = QDockWidget("Hierarchy", self)
        self.tree = QTreeWidget(); self.tree.setHeaderLabel("UI Tree")
        self.tree.itemClicked.connect(self.on_tree_click)
        self.tree.currentItemChanged.connect(self.on_tree_current_changed)
        self.tree.setToolTip("UI hierarchy. Use arrow keys to navigate; Enter to lock/unlock selection.")
        d.setWidget(self.tree); self.addDockWidget(Qt.RightDockWidgetArea, d)

    def setup_inspector_dock(self):
        d = QDockWidget("Inspector", self); tabs = QTabWidget()
        
        # Properties Tab (The one missing data in your screenshot)
        self.tbl_props = QTableWidget(); self.tbl_props.setColumnCount(2)
        self.tbl_props.setHorizontalHeaderLabels(["Property", "Value"])
        self.tbl_props.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_props.verticalHeader().setVisible(False)
        tabs.addTab(self.tbl_props, "Node Details")
        
        # Selectors Tab (Leandro's Requirement)
        w_loc = QWidget(); l_loc = QVBoxLayout(w_loc)
        self.combo_fmt = QComboBox(); self.combo_fmt.addItems(["Python (Appium)", "Java (By.xpath)", "Raw XPath"])
        self.combo_fmt.currentIndexChanged.connect(self.update_locators_text)
        self.combo_fmt.setToolTip("Change the code format for generated locators.")
        self.txt_loc = QTextEdit(); self.txt_loc.setReadOnly(True)
        l_loc.addWidget(self.combo_fmt); l_loc.addWidget(self.txt_loc)
        tabs.addTab(w_loc, "Smart Selectors")
        
        # Logcat Tab
        self.txt_log = QTextEdit(); self.txt_log.setReadOnly(True)
        self.txt_log.setToolTip("Live device log output. Offline snapshots load logcat.txt here.")
        tabs.addTab(self.txt_log, "Logcat")

        # System Log Tab
        self.txt_sys = QTextEdit(); self.txt_sys.setReadOnly(True)
        self.txt_sys.setToolTip("Internal app events, status updates, and diagnostics.")
        tabs.addTab(self.txt_sys, "System Log")
        
        d.setWidget(tabs); self.addDockWidget(Qt.BottomDockWidgetArea, d)

    # --- Core Logic ---

    def log_sys(self, message: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.txt_sys.append(f"[{ts}] {message}")

    def refresh_devices(self):
        self.combo_dev.blockSignals(True); self.combo_dev.clear()
        devs = AdbManager.get_devices_detailed()
        for d in devs:
            self.combo_dev.addItem(f"{d['model']} ({d['serial']})", d['serial'])
            AdbManager.record_device(d['serial'], d['model'])
        self.combo_dev.blockSignals(False)
        if devs: self.on_dev_change(0)
        self.update_history_combo()
        self.log_sys(f"Devices refreshed: {len(devs)} found")

    def on_dev_change(self, idx):
        self.active_device = self.combo_dev.itemData(idx)
        if self.active_device:
            self.log_sys(f"Active device set: {self.active_device}")

    def toggle_live(self):
        if self.video_thread:
            # Stop
            self.video_thread.stop(); self.video_thread = None
            self.xml_thread.stop(); self.xml_thread = None
            self.log_thread.stop(); self.log_thread = None
            self.focus_thread.stop(); self.focus_thread = None
            self.view.control_enabled = False
            self.btn_live.setText("START LIVE STREAM"); self.btn_live.setProperty("class", "primary")
            self.log_sys("Live mirror stopped")
        else:
            if not self.active_device:
                self.log_sys("Live mirror requested but no device is selected")
                return
            # Start
            self.txt_log.setText("Starting logcat...")
            self.video_thread = VideoThread(self.active_device)
            self.video_thread.frame_ready.connect(self.on_frame)
            self.video_thread.start()
            
            self.xml_thread = HierarchyThread(self.active_device)
            self.xml_thread.tree_ready.connect(self.on_tree_data)
            self.xml_thread.start()
            
            self.log_thread = LogcatThread(self.active_device)
            self.log_thread.log_line.connect(lambda l: self.txt_log.append(l))
            self.log_thread.start()
            
            self.focus_thread = FocusMonitorThread(self.active_device)
            self.focus_thread.focus_changed.connect(lambda f: self.lbl_focus.setText(f"Focus: {f}"))
            self.focus_thread.start()
            
            self.view.control_enabled = True
            self.btn_live.setText("STOP LIVE"); self.btn_live.setProperty("class", "danger")
            self.log_sys(f"Live mirror started on {self.active_device}")
        
        self.polish_btn(self.btn_live)

    def polish_btn(self, btn): btn.style().unpolish(btn); btn.style().polish(btn)

    def on_frame(self, data):
        img = QImage.fromData(data)
        if self.stream_max_size:
            if max(img.width(), img.height()) > self.stream_max_size:
                img = img.scaled(
                    self.stream_max_size,
                    self.stream_max_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
        if not self.pixmap_item:
            self.pixmap_item = self.scene.addPixmap(QPixmap.fromImage(img))
            self.pixmap_item.setZValue(0)
            self.handle_resize()
        else:
            self.pixmap_item.setPixmap(QPixmap.fromImage(img))
        self.fps_counter += 1

    def update_fps(self):
        self.lbl_fps.setText(f"FPS: {self.fps_counter}")
        self.fps_counter = 0

    def on_tree_data(self, xml_str, changed):
        if not changed and self.root_node: return
        
        root, parse_err = UixParser.parse(xml_str)
        self.root_node = root
        
        self.tree.clear(); self.current_node_map = {}; self.node_to_item_map = {}; self.rect_map = []
        if root:
            self.populate_tree(root, self.tree)
            if parse_err:
                self.log_sys("UI dump loaded but has zero valid bounds. The dump may be incomplete.")
        else:
            self.log_sys("UI dump parsed with no nodes. The dump may be invalid.")
        
        # Restore selection logic would go here
        
    def populate_tree(self, node, parent):
        name = f"{node.class_name.split('.')[-1]}"
        if node.resource_id: name += f" ({node.resource_id.split('/')[-1]})"
        elif node.text: name += f" \"{node.text}\""
        
        item = QTreeWidgetItem(parent); item.setText(0, name)
        self.current_node_map[id(item)] = node; self.node_to_item_map[id(node)] = item
        
        if node.valid_bounds: self.rect_map.append((node.rect, node))
        for c in node.children: self.populate_tree(c, item)

    def on_mouse_hover(self, x, y):
        self.lbl_coords.setText(f"X: {x}, Y: {y}")
        # Hover detection
        best_node = None; best_area = float('inf')
        for rect, node in self.rect_map:
            rx, ry, rw, rh = rect
            if rx <= x <= rx+rw and ry <= y <= ry+rh:
                area = rw * rh
                if area < best_area: best_area = area; best_node = node
        
        if best_node:
            self.view.setCursor(Qt.PointingHandCursor if best_node.clickable else Qt.ArrowCursor)
            if self.auto_follow_hover and not self.locked_node:
                self.select_node(best_node, scroll=True)

    def handle_tap(self, x, y):
        if self.video_thread: AdbManager.tap(self.active_device, x, y)
        else:
            # Lock selection in offline mode
            node = self.find_node_at(x, y)
            if node:
                self.toggle_lock(node)

    def handle_swipe(self, x1, y1, x2, y2):
        if self.video_thread: AdbManager.swipe(self.active_device, x1, y1, x2, y2)

    def select_node(self, node, scroll=True):
        x, y, w, h = node.rect
        self.rect_item.setRect(QRectF(x, y, w, h)); self.rect_item.show()
        
        # Populate Table (Restored missing data!)
        data = [
            ("Index", node.index), ("Text", node.text), ("Resource-ID", node.resource_id),
            ("Class", node.class_name), ("Package", node.package), ("Content-Desc", node.content_desc),
            ("Checkable", str(node.checkable)), ("Checked", str(node.checked)),
            ("Clickable", str(node.clickable)), ("Enabled", str(node.enabled)),
            ("Focusable", str(node.focusable)), ("Focused", str(node.focused)),
            ("Scrollable", str(node.scrollable)), ("Password", str(node.password)),
            ("Selected", str(node.selected)), ("Bounds", node.bounds_str)
        ]
        
        self.tbl_props.setRowCount(0)
        for i, (k,v) in enumerate(data):
            self.tbl_props.insertRow(i)
            self.tbl_props.setItem(i, 0, QTableWidgetItem(k))
            self.tbl_props.setItem(i, 1, QTableWidgetItem(v))
        
        self.generate_selectors(node)
        
        if scroll:
            item = self.node_to_item_map.get(id(node))
            if item:
                self.expand_to_item(item)
                self.tree.blockSignals(True)
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                self.tree.blockSignals(False)

    def generate_selectors(self, node):
        self.current_suggestions = LocatorSuggester.generate_locators(node, self.root_node)
        self.update_locators_text()

    def update_locators_text(self):
        if not hasattr(self, 'current_suggestions'): return
        fmt = self.combo_fmt.currentText()
        out = ""
        
        for s in self.current_suggestions:
            xpath = s['xpath']
            # Formatting logic for Leandro's Python/Appium requirement
            if "Python" in fmt:
                code = f'driver.find_element(AppiumBy.XPATH, "{xpath}")'
            elif "Java" in fmt:
                code = f'driver.findElement(By.xpath("{xpath}"));'
            else:
                code = xpath
                
            prefix = "PRIMARY" if s['type'].startswith("Scoped") else "ALT"
            out += f"[{prefix}] {s['type']}\n{code}\n\n"
            
        self.txt_loc.setText(out)

    def on_tree_click(self, item, col):
        node = self.current_node_map.get(id(item))
        if node:
            self.toggle_lock(node)
            self.select_node(node, scroll=False)

    def capture_snapshot(self):
        if not self.active_device: return
        d = QFileDialog.getExistingDirectory(self, "Save Snapshot")
        if d:
            path = os.path.join(d, f"snap_{int(time.time())}")
            AdbManager.capture_snapshot(self.active_device, path)
            self.load_snapshot(path)

    def load_snapshot_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Snapshot Dump",
            "",
            "UIX Dump (*.uix);;All Files (*)"
        )
        if file_path:
            self.load_snapshot(os.path.dirname(file_path))
            return

        d = QFileDialog.getExistingDirectory(self, "Open Snapshot Folder")
        if d:
            self.load_snapshot(d)

    def load_snapshot(self, path):
        # Stop live mode if active
        if self.video_thread: self.toggle_live()
        
        # Load Screenshot
        png = os.path.join(path, "screenshot.png")
        if os.path.exists(png):
            if self.pixmap_item:
                self.scene.removeItem(self.pixmap_item)
                self.pixmap_item = None

            if self.rect_item.scene() is None:
                self.rect_item = QGraphicsRectItem()
                self.rect_item.setPen(QPen(QColor(Theme.BMW_BLUE), 3))
                self.rect_item.setZValue(99)
                self.scene.addItem(self.rect_item)
                self.rect_item.hide()

            self.pixmap_item = self.scene.addPixmap(QPixmap(png))
            self.handle_resize()
            
        # Load XML
        xml = os.path.join(path, "dump.uix")
        if os.path.exists(xml):
            with open(xml, 'r', encoding='utf-8') as f:
                self.on_tree_data(f.read(), True)
        else:
            self.log_sys("No dump.uix found in snapshot folder.")

        # Load logcat (offline)
        logcat_path = os.path.join(path, "logcat.txt")
        if os.path.exists(logcat_path):
            with open(logcat_path, "r", encoding="utf-8", errors="replace") as f:
                self.txt_log.setText(f.read())
        else:
            self.txt_log.setText("No logcat file found in this snapshot.")

        self.log_sys(f"Loaded snapshot: {path}")
        
        self.setWindowTitle(f"QUANTUM Inspector - {os.path.basename(path)}")

    def update_history_combo(self) -> None:
        self.combo_history.blockSignals(True)
        self.combo_history.clear()
        entries = AdbManager.load_device_history()
        for e in entries:
            serial = e.get("serial", "")
            model = e.get("model", "Unknown")
            self.combo_history.addItem(f"{model} ({serial})", serial)
        self.combo_history.blockSignals(False)

    def connect_ip_device(self) -> None:
        addr = self.input_ip.text().strip()
        if not addr:
            return
        res = AdbManager.connect_ip(addr)
        self.log_sys(f"ADB connect {addr}: {res}")
        self.refresh_devices()

    def reconnect_history(self) -> None:
        serial = self.combo_history.currentData()
        if not serial:
            return
        if ":" in serial:
            res = AdbManager.connect_ip(serial)
            self.log_sys(f"ADB connect {serial}: {res}")
        self.refresh_devices()

    def on_stream_size_change(self) -> None:
        text = self.combo_res.currentText()
        if text == "Native":
            self.stream_max_size = None
            self.log_sys("Stream size set to native resolution")
        else:
            self.stream_max_size = int(text)
            self.log_sys(f"Stream max size set to {self.stream_max_size}")

    def toggle_auto_follow(self) -> None:
        self.auto_follow_hover = self.chk_auto_follow.isChecked()
        self.log_sys(f"Auto locate hover: {'on' if self.auto_follow_hover else 'off'}")

    def toggle_ambient(self) -> None:
        self.ambient_enabled = self.chk_ambient.isChecked()
        if not self.ambient_enabled:
            self.ambient_timer.stop()
            QApplication.instance().setStyleSheet(Theme.get_stylesheet())
        else:
            self.ambient_timer.start(250)
        self.log_sys(f"Ambient glow: {'on' if self.ambient_enabled else 'off'}")

    def update_ambient(self) -> None:
        if not self.ambient_enabled:
            return
        self.ambient_phase += 0.08
        r = int(20 + 15 * (1 + math.sin(self.ambient_phase)))
        b = int(40 + 30 * (1 + math.cos(self.ambient_phase * 0.7)))
        overlay = f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(15, 20, {b}, 255), stop:1 rgba({r}, 30, 60, 255));"
        QApplication.instance().setStyleSheet(Theme.get_stylesheet(ambient_overlay=overlay))

    def expand_to_item(self, item: QTreeWidgetItem) -> None:
        cur = item
        while cur:
            cur.setExpanded(True)
            cur = cur.parent()

    def find_node_at(self, x: int, y: int):
        best_node = None
        best_area = float('inf')
        for rect, node in self.rect_map:
            rx, ry, rw, rh = rect
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                area = rw * rh
                if area < best_area:
                    best_area = area
                    best_node = node
        return best_node

    def set_lock(self, node) -> None:
        self.locked_node = True
        self.locked_node_id = id(node)
        self.rect_item.setPen(QPen(QColor(Theme.ACCENT_YELLOW), 3))
        self.log_sys("Selection locked")

    def clear_lock(self) -> None:
        self.locked_node = False
        self.locked_node_id = None
        self.rect_item.setPen(QPen(QColor(Theme.BMW_BLUE), 3))
        self.log_sys("Selection unlocked")

    def toggle_lock(self, node) -> None:
        if self.locked_node and self.locked_node_id == id(node):
            self.clear_lock()
        else:
            self.set_lock(node)

    def on_tree_current_changed(self, current, previous) -> None:
        if not current:
            return
        if self.locked_node:
            return
        node = self.current_node_map.get(id(current))
        if node:
            self.select_node(node, scroll=False)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            item = self.tree.currentItem()
            if item:
                node = self.current_node_map.get(id(item))
                if node:
                    self.toggle_lock(node)
                    self.select_node(node, scroll=False)
                    return
        super().keyPressEvent(event)

    def enable_fit(self): self.auto_fit = True; self.handle_resize()
    def disable_fit(self): self.auto_fit = False; self.view.resetTransform()
    def handle_resize(self):
        if self.auto_fit and self.pixmap_item: self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
