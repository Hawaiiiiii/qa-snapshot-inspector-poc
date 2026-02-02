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
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QFileDialog, QTextEdit,
    QGroupBox, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QToolBar, QTabWidget, QStatusBar, QFrame, QDockWidget, QApplication, QLineEdit, QCheckBox
)
from PySide6.QtGui import QPixmap, QPen, QBrush, QImage, QColor, QAction, QPainter, QCursor, QLinearGradient, QPalette
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
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

class AmbientPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ambient_pixmap = None
        self._ambient_opacity = 0.22
        self._overlay_color = QColor(10, 14, 22, 140)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

    def set_ambient_pixmap(self, pixmap: QPixmap) -> None:
        self._ambient_pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if self._ambient_pixmap and not self._ambient_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.setOpacity(self._ambient_opacity)
            painter.drawPixmap(self.rect(), self._ambient_pixmap)
            painter.setOpacity(1.0)
            painter.fillRect(self.rect(), self._overlay_color)
            painter.end()
        super().paintEvent(event)

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
        self.ambient_offset = 0.0
        self.ambient_widgets = []
        self.ambient_panels = []
        self.ambient_player = None
        self.ambient_audio = None
        self.ambient_sink = None
        self.ambient_enabled = True
        self.ambient_last_hash = None
        self.ambient_prev_image = None
        self.ambient_last_frame_ts = 0.0
        self.ambient_frame_interval_ms = 90
        self.ambient_static_frame = None
        self.perf_mode = False
        self.last_tree_update = 0.0
        self.last_snapshot_path = None
        self.device_profiles = []
        self.auto_fit = True
        self.fps_counter = 0
        
        self.setup_ui()
        self.refresh_devices()

        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)

        self.ambient_timer = QTimer()
        self.ambient_timer.timeout.connect(self.update_ambient)

    def setup_ui(self):
        central = QWidget(); central_lay = QVBoxLayout(central); central_lay.setContentsMargins(0,0,0,0)
        
        # Toolbar
        tb = QToolBar()
        self.toolbar = tb
        self.register_ambient_widget(tb)
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
        self.view.setStyleSheet(f"background-color: {Theme.BG_DARK};")
        self.view.setBackgroundBrush(QBrush(QColor(Theme.BG_DARK)))
        self.view.viewport().setAutoFillBackground(True)
        self.view.viewport().setStyleSheet(f"background-color: {Theme.BG_DARK};")
        self.view.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.view.setBackgroundBrush(QBrush(QColor(Theme.BG_DARK)))
        self.view.mouse_moved.connect(self.on_mouse_hover)
        self.view.input_tap.connect(self.handle_tap)
        self.view.input_swipe.connect(self.handle_swipe)
        self.view.view_resized.connect(self.handle_resize)
        central_lay.addWidget(self.view)
        
        self.setCentralWidget(central)
        central.setAutoFillBackground(True)
        pal = central.palette()
        pal.setColor(QPalette.Window, QColor(Theme.BG_DARK))
        central.setPalette(pal)

        # Docks
        self.setup_control_dock()
        self.setup_tree_dock()
        self.setup_inspector_dock()
        self.setup_syslog_dock()

        self.init_ambient_video()

        # Overlay Items
        self.rect_item = QGraphicsRectItem()
        self.rect_item.setPen(QPen(QColor(Theme.BMW_BLUE), 3))
        self.rect_item.setZValue(99)
        self.scene.addItem(self.rect_item); self.rect_item.hide()
        self.pixmap_item = None

    def setup_control_dock(self):
        d = QDockWidget("Environment", self); w = QWidget(); l = QVBoxLayout(w)
        self.dock_env = d
        self.register_ambient_widget(d)
        
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

        prof_row = QHBoxLayout()
        self.combo_profiles = QComboBox()
        self.combo_profiles.setToolTip("Device profiles from devices.json (optional).")
        self.combo_profiles.currentIndexChanged.connect(self.apply_profile)
        self.btn_reload_profiles = QPushButton("Reload Profiles")
        self.btn_reload_profiles.clicked.connect(self.load_device_profiles)
        self.btn_reload_profiles.setToolTip("Reload device profiles from devices.json.")
        prof_row.addWidget(self.combo_profiles); prof_row.addWidget(self.btn_reload_profiles)

        gl.addWidget(self.combo_dev); gl.addWidget(btn_ref)
        gl.addLayout(ip_row)
        gl.addLayout(hist_row)
        gl.addLayout(prof_row)
        gb_dev.setLayout(gl); l.addWidget(gb_dev)
        
        # Live Modes
        gb_live = QGroupBox("Live Mirror"); ll = QVBoxLayout()
        self.btn_live = QPushButton("START LIVE STREAM"); self.btn_live.setProperty("class", "primary")
        self.btn_live.clicked.connect(self.toggle_live)
        self.chk_turbo = QLabel("Optimized"); self.chk_turbo.setStyleSheet("color: #8aa1c1; font-size: 9pt;")
        self.btn_live.setToolTip("Start or stop live mirroring and control input.")

        res_row = QHBoxLayout()
        self.combo_res = QComboBox()
        self.combo_res.addItems(["Native", "4K", "2K", "1080p", "720p", "1024"])
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
        self.btn_recapture = QPushButton("Re-Capture Last"); self.btn_recapture.clicked.connect(self.recapture_last_snapshot)
        self.btn_recapture.setToolTip("Re-capture the last loaded snapshot using the active device.")
        self.btn_recapture.setEnabled(False)
        sl.addWidget(btn_cap); sl.addWidget(btn_load); sl.addWidget(self.btn_recapture)
        gb_snap.setLayout(sl); l.addWidget(gb_snap)

        gb_opts = QGroupBox("UX Options"); ol = QVBoxLayout()
        self.chk_auto_follow = QCheckBox("Auto Locate Hover")
        self.chk_auto_follow.setChecked(True)
        self.chk_auto_follow.stateChanged.connect(self.toggle_auto_follow)
        self.chk_auto_follow.setToolTip("Auto-scroll the UI Tree to the element under the cursor.")

        self.chk_ambient = QCheckBox("Ambient Video")
        self.chk_ambient.setChecked(True)
        self.chk_ambient.stateChanged.connect(self.toggle_ambient_video)
        self.chk_ambient.setToolTip("Animate the dock panels only. Live view stays clean.")

        self.chk_perf = QCheckBox("Performance Mode")
        self.chk_perf.setChecked(False)
        self.chk_perf.stateChanged.connect(self.toggle_perf_mode)
        self.chk_perf.setToolTip("Reduce UI tree refresh rate while live streaming.")

        ol.addWidget(self.chk_auto_follow); ol.addWidget(self.chk_ambient); ol.addWidget(self.chk_perf)
        gb_opts.setLayout(ol); l.addWidget(gb_opts)
        
        l.addStretch()
        d.setWidget(self.wrap_ambient_panel(w)); self.addDockWidget(Qt.LeftDockWidgetArea, d)
        self.load_device_profiles()

    def setup_tree_dock(self):
        d = QDockWidget("Hierarchy", self)
        self.dock_tree = d
        self.register_ambient_widget(d)
        self.tree = QTreeWidget(); self.tree.setHeaderLabel("UI Tree")
        self.tree.itemClicked.connect(self.on_tree_click)
        self.tree.currentItemChanged.connect(self.on_tree_current_changed)
        self.tree.setToolTip("UI hierarchy. Use arrow keys to navigate; Enter to lock/unlock selection.")
        d.setWidget(self.wrap_ambient_panel(self.tree)); self.addDockWidget(Qt.RightDockWidgetArea, d)

    def setup_inspector_dock(self):
        d = QDockWidget("Inspector", self); tabs = QTabWidget()
        self.dock_inspector = d
        self.register_ambient_widget(d)
        
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

        
        
        d.setWidget(self.wrap_ambient_panel(tabs)); self.addDockWidget(Qt.BottomDockWidgetArea, d)

    def setup_syslog_dock(self):
        d = QDockWidget("System Log", self)
        self.dock_syslog = d
        self.register_ambient_widget(d)
        self.txt_sys = QTextEdit(); self.txt_sys.setReadOnly(True)
        self.txt_sys.setToolTip("Internal app events, status updates, and diagnostics.")
        d.setWidget(self.wrap_ambient_panel(self.txt_sys)); self.addDockWidget(Qt.BottomDockWidgetArea, d)

    # --- Core Logic ---

    def log_sys(self, message: str) -> None:
        if not hasattr(self, "txt_sys"):
            return
        ts = time.strftime("%H:%M:%S")
        self.txt_sys.append(f"[{ts}] {message}")

    def register_ambient_widget(self, widget) -> None:
        if widget not in self.ambient_widgets:
            self.ambient_widgets.append(widget)
        if hasattr(widget, "setAttribute"):
            widget.setAttribute(Qt.WA_StyledBackground, True)

    def wrap_ambient_panel(self, widget: QWidget) -> QWidget:
        panel = AmbientPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        self.ambient_panels.append(panel)
        return panel

    def init_ambient_video(self) -> None:
        root = Path(__file__).resolve().parents[2]
        video_path = root / "assets" / "fui_hmi_ux" / "UX.webm"
        if not video_path.exists():
            self.log_sys("Ambient video not found. Background disabled.")
            self.ambient_enabled = False
            return

        self.ambient_sink = QVideoSink()
        self.ambient_sink.videoFrameChanged.connect(self.on_ambient_frame)

        self.ambient_player = QMediaPlayer(self)
        self.ambient_audio = QAudioOutput(self)
        self.ambient_audio.setVolume(0.0)
        self.ambient_player.setAudioOutput(self.ambient_audio)
        self.ambient_player.setVideoOutput(self.ambient_sink)
        self.ambient_player.setSource(QUrl.fromLocalFile(str(video_path)))
        self.ambient_player.mediaStatusChanged.connect(self.on_ambient_status)

        if self.ambient_enabled:
            self.ambient_player.play()
            self.apply_chrome_overlay(translucent=True)
            self.log_sys("Ambient video loaded")

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

        if self.perf_mode and self.video_thread:
            now = time.time()
            if now - self.last_tree_update < 1.5:
                return
            self.last_tree_update = now
        
        root, parse_err = UixParser.parse(xml_str)
        self.root_node = root
        
        self.tree.clear(); self.current_node_map = {}; self.node_to_item_map = {}; self.rect_map = []
        if root:
            self.populate_tree(root, self.tree)
            if parse_err:
                self.log_sys("UI dump loaded but has zero valid bounds. The dump may be incomplete.")
        else:
            self.log_sys("UI dump parsed with no nodes. The dump may be invalid.")

        if root and not self.rect_map:
            self.log_sys("Snapshot flagged: zero valid element bounds detected.")
        
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
            self.last_snapshot_path = path
            self.btn_recapture.setEnabled(True)
            self.log_sys(f"Snapshot captured: {path}")

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
        self.last_snapshot_path = path
        self.btn_recapture.setEnabled(True)
        
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

    def load_device_profiles(self) -> None:
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()

        root = Path(__file__).resolve().parents[3]
        config_path = root / "devices.json"
        profiles = []
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                profiles = data.get("profiles") or data.get("known_devices") or []
            except Exception:
                profiles = []

        for p in profiles:
            serial = p.get("serial", "")
            model = p.get("model", "Unknown")
            self.combo_profiles.addItem(f"{model} ({serial})", p)

        self.combo_profiles.blockSignals(False)
        self.log_sys(f"Device profiles loaded: {len(profiles)}")

    def apply_profile(self) -> None:
        profile = self.combo_profiles.currentData()
        if not isinstance(profile, dict):
            return
        serial = profile.get("serial", "")
        if serial:
            self.input_ip.setText(serial)
            self.log_sys(f"Profile selected: {serial}")

        max_size = profile.get("max_size")
        if max_size:
            max_size_str = str(max_size)
            idx = self.combo_res.findText(max_size_str)
            if idx != -1:
                self.combo_res.setCurrentIndex(idx)

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
            return

        mapping = {
            "4K": 2160,
            "2K": 1440,
            "1080p": 1080,
            "720p": 720,
            "1024": 1024,
        }
        self.stream_max_size = mapping.get(text, 1024)
        self.log_sys(f"Stream max size set to {text} ({self.stream_max_size})")

    def toggle_auto_follow(self) -> None:
        self.auto_follow_hover = self.chk_auto_follow.isChecked()
        self.log_sys(f"Auto locate hover: {'on' if self.auto_follow_hover else 'off'}")

    def toggle_ambient_video(self) -> None:
        self.ambient_enabled = self.chk_ambient.isChecked()
        if not self.ambient_enabled:
            if self.ambient_player:
                self.ambient_player.pause()
            self.apply_chrome_overlay(translucent=False)
            self.ambient_static_frame = None
        else:
            if self.ambient_player:
                self.ambient_player.play()
            self.apply_chrome_overlay(translucent=True)
        self.log_sys(f"Ambient video: {'on' if self.ambient_enabled else 'off'}")

    def update_ambient(self) -> None:
        if not self.ambient_enabled:
            return
        self.ambient_phase += 0.08
        self.ambient_offset = (self.ambient_offset + 0.35) % 24
        self.apply_chrome_overlay(translucent=False)

    def on_ambient_status(self, status) -> None:
        if not self.ambient_player:
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.ambient_player.setPosition(0)
            self.ambient_player.play()

    def apply_chrome_overlay(self, translucent: bool) -> None:
        overlay = "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(12, 18, 34, 255), stop:1 rgba(18, 28, 60, 255));"
        QApplication.instance().setStyleSheet(Theme.get_stylesheet(ambient_overlay=overlay, use_translucent=translucent))

    def apply_led_fallback(self) -> None:
        return

    def apply_ambient_brush(self, widget, brush: QBrush) -> None:
        pal = widget.palette()
        pal.setBrush(QPalette.Window, brush)
        widget.setAutoFillBackground(True)
        widget.setPalette(pal)
        widget.update()

    def soft_blur(self, img: QImage) -> QImage:
        # Mild blur by downscale/upscale + gentle dark overlay
        w = max(96, img.width() // 4)
        h = max(96, img.height() // 4)
        small = img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        blurred = small.scaled(img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        painter = QPainter(blurred)
        painter.fillRect(blurred.rect(), QColor(8, 12, 20, 90))
        painter.end()
        return blurred

    def blend_ambient(self, img: QImage) -> QImage:
        # Temporal smoothing to reduce flicker
        if self.ambient_prev_image is None:
            self.ambient_prev_image = img
            return img

        blended = QImage(img.size(), QImage.Format_ARGB32)
        blended.fill(QColor(0, 0, 0, 0))
        painter = QPainter(blended)
        painter.setOpacity(0.7)
        painter.drawImage(0, 0, self.ambient_prev_image)
        painter.setOpacity(0.3)
        painter.drawImage(0, 0, img)
        painter.end()
        self.ambient_prev_image = blended
        return blended

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

    def recapture_last_snapshot(self) -> None:
        if not self.last_snapshot_path:
            self.log_sys("No snapshot available to re-capture")
            return
        if not self.active_device:
            self.log_sys("Re-capture requested but no device is selected")
            return
        AdbManager.capture_snapshot(self.active_device, self.last_snapshot_path)
        self.load_snapshot(self.last_snapshot_path)
        self.log_sys(f"Snapshot re-captured: {self.last_snapshot_path}")

    def toggle_perf_mode(self) -> None:
        self.perf_mode = self.chk_perf.isChecked()
        if self.perf_mode:
            self.ambient_frame_interval_ms = 140
        else:
            self.ambient_frame_interval_ms = 90
        self.log_sys(f"Performance mode: {'on' if self.perf_mode else 'off'}")

    def enable_fit(self): self.auto_fit = True; self.handle_resize()
    def disable_fit(self): self.auto_fit = False; self.view.resetTransform()
    def handle_resize(self):
        if self.auto_fit and self.pixmap_item: self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def on_ambient_frame(self, frame) -> None:
        if not self.ambient_enabled:
            return
        if not frame or not frame.isValid():
            return
        now = time.monotonic()
        if (now - self.ambient_last_frame_ts) * 1000.0 < self.ambient_frame_interval_ms:
            return
        self.ambient_last_frame_ts = now
        img = frame.toImage()
        if img.isNull():
            return
        if self.perf_mode:
            if self.ambient_static_frame is None:
                if img.width() > 640:
                    img = img.scaledToWidth(640, Qt.SmoothTransformation)
                self.ambient_static_frame = QPixmap.fromImage(img)
            pixmap = self.ambient_static_frame
        else:
            if img.width() > 720:
                img = img.scaledToWidth(720, Qt.SmoothTransformation)
            img = self.soft_blur(self.blend_ambient(img))
            pixmap = QPixmap.fromImage(img)
        for panel in self.ambient_panels:
            panel.set_ambient_pixmap(pixmap)
