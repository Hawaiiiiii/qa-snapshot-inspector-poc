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
import re
import shutil
import threading
import urllib.request
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QFileDialog, QTextEdit,
    QGroupBox, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QToolBar, QTabWidget, QStatusBar, QFrame, QDockWidget, QApplication, QLineEdit, QCheckBox, QMessageBox
)
from PySide6.QtGui import QPixmap, QPen, QBrush, QImage, QColor, QAction, QPainter, QCursor, QLinearGradient, QPalette
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
from PySide6.QtCore import Qt, QRectF, Signal, QTimer

from qa_snapshot_tool.uix_parser import UixParser
from qa_snapshot_tool.locator_suggester import LocatorSuggester
from qa_snapshot_tool.adb_manager import AdbManager
from qa_snapshot_tool.live_mirror import VideoThread, ScrcpyVideoSource, HierarchyThread, LogcatThread, FocusMonitorThread
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
        self.stream_scale = 1.0
        self.dump_bounds = None
        self.device_bounds = None
        self.last_frame_size = None
        self.last_frame_image = None
        self.live_source = "ADB"
        self.scrcpy_path = ""
        self.selected_display_id = None
        self._root_prompted = False
        scrcpy_root = Path(__file__).resolve().parents[2] / "scrcpy-3.3.4"
        scrcpy_git_repo = scrcpy_root / "scrcpy-git"
        scrcpy_snapshot_repo = scrcpy_root / "scrcpy-3.3.4"
        self.scrcpy_repo_path = str(scrcpy_git_repo if (scrcpy_git_repo / ".git").exists() else scrcpy_snapshot_repo)
        self.prefer_raw_scrcpy = True
        
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
        self.lbl_tree_status = QLabel("Tree: Unknown"); self.lbl_tree_status.setStyleSheet("color: #9aa7bd; font-weight: 600;")
        
        act_fit = QAction("Fit Screen", self); act_fit.triggered.connect(self.enable_fit)
        act_11 = QAction("1:1 Pixel", self); act_11.triggered.connect(self.disable_fit)
        
        tb.addWidget(self.lbl_fps); tb.addWidget(self.lbl_coords); tb.addSeparator(); tb.addWidget(self.lbl_focus)
        tb.addSeparator(); tb.addWidget(self.lbl_tree_status)
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

        adb_row = QHBoxLayout()
        self.input_adb_server = QLineEdit()
        self.input_adb_server.setPlaceholderText("ADB server host:port (optional)")
        self.input_adb_server.setToolTip("Route ADB through a remote server (device farm / emulator).")
        self.btn_set_adb_server = QPushButton("Set ADB Server")
        self.btn_set_adb_server.clicked.connect(self.set_adb_server)
        adb_row.addWidget(self.input_adb_server); adb_row.addWidget(self.btn_set_adb_server)

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
        gl.addLayout(adb_row)
        gl.addLayout(prof_row)
        gb_dev.setLayout(gl); l.addWidget(gb_dev)
        
        # Live Modes
        gb_live = QGroupBox("Live Mirror"); ll = QVBoxLayout()
        self.btn_live = QPushButton("START LIVE STREAM"); self.btn_live.setProperty("class", "primary")
        self.btn_live.clicked.connect(self.toggle_live)
        self.chk_turbo = QLabel("Optimized"); self.chk_turbo.setStyleSheet("color: #8aa1c1; font-size: 9pt;")
        self.btn_live.setToolTip("Start or stop live mirroring and control input.")

        src_row = QHBoxLayout()
        lbl_src = QLabel("Video Source")
        self.combo_live_source = QComboBox()
        self.combo_live_source.addItems(["Scrcpy (fast)", "ADB (compat)"])
        self.combo_live_source.setToolTip("Select the live video backend.")
        src_row.addWidget(lbl_src); src_row.addWidget(self.combo_live_source)

        scrcpy_row = QHBoxLayout()
        lbl_scrcpy = QLabel("Scrcpy Exe")
        self.input_scrcpy = QLineEdit()
        self.input_scrcpy.setPlaceholderText("Auto-detect from PATH")
        self.input_scrcpy.setToolTip("Optional path to scrcpy.exe (preferred over PATH).")
        self.btn_scrcpy = QPushButton("Browse")
        self.btn_scrcpy.clicked.connect(self.browse_scrcpy)
        scrcpy_row.addWidget(lbl_scrcpy); scrcpy_row.addWidget(self.input_scrcpy); scrcpy_row.addWidget(self.btn_scrcpy)

        default_scrcpy = shutil.which("scrcpy")
        if default_scrcpy:
            self.input_scrcpy.setText(default_scrcpy)
            self.scrcpy_path = default_scrcpy

        self.chk_scrcpy_auto = QCheckBox("Auto-update scrcpy (git pull)")
        self.chk_scrcpy_auto.setChecked(False)
        self.chk_scrcpy_auto.setToolTip("If scrcpy source is a git repo, pull latest before starting stream.")

        self.chk_scrcpy_hide = QCheckBox("Show scrcpy window")
        self.chk_scrcpy_hide.setChecked(False)
        self.chk_scrcpy_hide.setToolTip("Uncheck to keep scrcpy hidden. Check to show the scrcpy window.")
        self.chk_scrcpy_hide.stateChanged.connect(self.on_scrcpy_window_toggle)

        self.chk_scrcpy_raw = QCheckBox("Prefer raw H.264 stream (PyAV)")
        self.chk_scrcpy_raw.setChecked(True)
        self.chk_scrcpy_raw.setToolTip("Uses raw H.264 decode for higher FPS when PyAV is installed.")
        self.chk_scrcpy_raw.stateChanged.connect(self.on_scrcpy_window_toggle)

        res_row = QHBoxLayout()
        self.combo_res = QComboBox()
        self.combo_res.addItems(["Native", "4K", "2K", "1080p", "720p", "1024"])
        self.combo_res.currentIndexChanged.connect(self.on_stream_size_change)
        self.combo_res.setToolTip("Reduce stream resolution for better performance.")
        lbl_res = QLabel("Max Size"); lbl_res.setToolTip("Maximum stream width/height (preserves aspect ratio).")
        res_row.addWidget(lbl_res); res_row.addWidget(self.combo_res)

        display_row = QHBoxLayout()
        lbl_display = QLabel("Display")
        self.combo_display = QComboBox()
        self.combo_display.setToolTip("Select which display to capture for scrcpy/ADB dumps. Auto uses the best match.")
        self.combo_display.currentIndexChanged.connect(self.on_display_change)
        display_row.addWidget(lbl_display); display_row.addWidget(self.combo_display)

        ll.addWidget(self.btn_live); ll.addWidget(self.chk_turbo); ll.addLayout(src_row); ll.addLayout(scrcpy_row)
        ll.addWidget(self.chk_scrcpy_auto); ll.addWidget(self.chk_scrcpy_hide); ll.addWidget(self.chk_scrcpy_raw); ll.addLayout(res_row); ll.addLayout(display_row)
        gb_live.setLayout(ll); l.addWidget(gb_live)

        # Device Actions
        gb_actions = QGroupBox("Device Actions"); al = QVBoxLayout()
        self.btn_wake = QPushButton("Wake Screen")
        self.btn_wake.setToolTip("Turns the device screen on and attempts to unlock it.")
        self.btn_wake.clicked.connect(self.wake_screen)
        self.btn_sleep = QPushButton("Sleep Screen")
        self.btn_sleep.setToolTip("Turns the device screen off (saves power, scrcpy will go black).")
        self.btn_sleep.clicked.connect(self.sleep_screen)
        self.chk_stay_awake = QCheckBox("Keep Screen Awake (USB)")
        self.chk_stay_awake.setToolTip("Keeps the screen on while connected to USB power.")
        self.chk_stay_awake.stateChanged.connect(self.toggle_stay_awake)
        al.addWidget(self.btn_wake); al.addWidget(self.btn_sleep); al.addWidget(self.chk_stay_awake)
        gb_actions.setLayout(al); l.addWidget(gb_actions)
        
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

    def browse_scrcpy(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select scrcpy executable",
            "",
            "scrcpy executable (scrcpy.exe);;All Files (*)",
        )
        if path:
            self.input_scrcpy.setText(path)
            self.log_sys(f"Scrcpy path set: {path}")

    def find_scrcpy_binary(self) -> str:
        repo_path = Path(self.scrcpy_repo_path)
        candidates = [
            repo_path / "scrcpy.exe",
            repo_path / "app" / "scrcpy.exe",
            repo_path / "app" / "build" / "scrcpy.exe",
            repo_path / "app" / "dist" / "scrcpy.exe",
            repo_path / "x" / "app" / "scrcpy.exe",
        ]
        for cand in candidates:
            if cand.exists():
                return str(cand)
        return ""

    def find_scrcpy_server(self, scrcpy_bin: str) -> str:
        bin_path = Path(scrcpy_bin)
        candidates = []

        # Same folder as scrcpy.exe (release zip layout)
        candidates.append(bin_path.parent / "scrcpy-server")
        candidates.append(bin_path.parent / "scrcpy-server.jar")

        # Repo root (custom build layout) only if scrcpy lives under repo
        repo_path = Path(self.scrcpy_repo_path)
        if repo_path in bin_path.parents:
            candidates.append(repo_path / "scrcpy-server")
            candidates.append(repo_path / "scrcpy-server.jar")
            candidates.extend(sorted(repo_path.glob("scrcpy-server-v*")))

            # Two levels up from x/app/scrcpy.exe
            if bin_path.parts and "x" in bin_path.parts:
                try:
                    root = bin_path.parents[2]
                    candidates.append(root / "scrcpy-server")
                    candidates.append(root / "scrcpy-server.jar")
                    candidates.extend(sorted(root.glob("scrcpy-server-v*")))
                except Exception:
                    pass

        for cand in candidates:
            if cand and cand.exists() and cand.is_file():
                return str(cand)
        return ""

    def resolve_scrcpy_path(self) -> str:
        manual = self.input_scrcpy.text().strip() if hasattr(self, "input_scrcpy") else ""
        if manual and Path(manual).exists():
            return manual
        auto = self.find_scrcpy_binary()
        if auto:
            return auto
        from shutil import which
        return which("scrcpy") or ""

    def update_scrcpy_repo(self) -> None:
        repo_path = Path(self.scrcpy_repo_path)
        git_dir = repo_path / ".git"
        if not repo_path.exists() or not git_dir.exists():
            scrcpy_root = Path(__file__).resolve().parents[2] / "scrcpy-3.3.4"
            git_repo = scrcpy_root / "scrcpy-git"
            if not git_repo.exists() or not (git_repo / ".git").exists():
                try:
                    git_repo.parent.mkdir(parents=True, exist_ok=True)
                    res = subprocess.run(
                        ["git", "clone", "--depth", "1", "https://github.com/Genymobile/scrcpy.git", str(git_repo)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if res.returncode != 0:
                        msg = res.stderr.strip() or res.stdout.strip() or "unknown error"
                        self.log_sys(f"Scrcpy auto-update failed (clone): {msg}")
                        return
                    self.log_sys("Scrcpy auto-update: cloned upstream repo")
                except Exception as ex:
                    self.log_sys(f"Scrcpy auto-update error: {ex}")
                    return
            self.scrcpy_repo_path = str(git_repo)
            repo_path = git_repo
            git_dir = repo_path / ".git"
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_path), "pull", "--ff-only"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                msg = res.stdout.strip() or "Scrcpy auto-update: up to date"
                self.log_sys(msg)
                self._build_scrcpy_async(repo_path)
            else:
                msg = res.stderr.strip() or res.stdout.strip() or "unknown error"
                self.log_sys(f"Scrcpy auto-update failed: {msg}")
        except Exception as ex:
            self.log_sys(f"Scrcpy auto-update error: {ex}")

    def _build_scrcpy_async(self, repo_path: Path) -> None:
        if not repo_path.exists():
            self.log_sys("Scrcpy build skipped (repo not found)")
            return

        def _worker() -> None:
            try:
                self._build_scrcpy(repo_path)
            except Exception as ex:
                self.log_sys(f"Scrcpy build failed: {ex}")

        threading.Thread(target=_worker, daemon=True).start()

    def _build_scrcpy(self, repo_path: Path) -> None:
        bash = Path("C:/msys64/usr/bin/bash.exe")
        if not bash.exists():
            self.log_sys("Scrcpy build skipped (MSYS2 not installed)")
            return

        version = self._detect_scrcpy_version(repo_path)
        if not version:
            self.log_sys("Scrcpy build skipped (version not detected)")
            return

        server_path = repo_path / f"scrcpy-server-v{version}"
        if not server_path.exists():
            if not self._download_scrcpy_server(version, server_path):
                self.log_sys("Scrcpy build skipped (server download failed)")
                return

        build_dir = repo_path / "x"
        build_cmd = "meson setup x"
        if build_dir.exists():
            build_cmd = "meson setup x --reconfigure"

        cmd = (
            f"export PATH=/usr/bin:/mingw64/bin:$PATH; "
            f"cd {self._msys_path(repo_path)} && "
            f"{build_cmd} --buildtype=release --strip -Db_lto=true "
            f"-Dprebuilt_server=./scrcpy-server-v{version} && ninja -Cx"
        )
        self.log_sys(f"Scrcpy build started (v{version})")
        res = subprocess.run([str(bash), "-lc", cmd], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            self.log_sys("Scrcpy build complete")
            self._copy_scrcpy_runtime_dlls(repo_path)
        else:
            msg = res.stderr.strip() or res.stdout.strip() or "unknown error"
            self.log_sys(f"Scrcpy build failed: {msg}")

    def _detect_scrcpy_version(self, repo_path: Path) -> str:
        meson_file = repo_path / "meson.build"
        if not meson_file.exists():
            return ""
        try:
            text = meson_file.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"version\s*:\s*'([^']+)'", text)
            return match.group(1).strip() if match else ""
        except Exception:
            return ""

    def _download_scrcpy_server(self, version: str, out_path: Path) -> bool:
        try:
            url = f"https://github.com/Genymobile/scrcpy/releases/download/v{version}/scrcpy-server-v{version}"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, out_path)
            return out_path.exists()
        except Exception as ex:
            self.log_sys(f"Scrcpy server download error: {ex}")
            return False

    def _msys_path(self, path: Path) -> str:
        drive = path.drive.rstrip(":").lower()
        tail = str(path).replace("\\", "/").split(":", 1)[-1]
        return f"/{drive}{tail}"

    def _copy_scrcpy_runtime_dlls(self, repo_path: Path) -> None:
        scrcpy_bin = repo_path / "x" / "app" / "scrcpy.exe"
        if not scrcpy_bin.exists():
            return
        dll_src = Path("C:/msys64/mingw64/bin")
        if not dll_src.exists():
            self.log_sys("Scrcpy DLL copy skipped (MSYS2 runtime not found)")
            return
        dlls = set()
        bash = Path("C:/msys64/usr/bin/bash.exe")
        if bash.exists():
            try:
                cmd = f"export PATH=/usr/bin:/mingw64/bin:$PATH; ldd '{self._msys_path(scrcpy_bin)}'"
                res = subprocess.run([str(bash), "-lc", cmd], capture_output=True, text=True, check=False)
                for line in (res.stdout or "").splitlines():
                    if "/mingw64/bin/" in line and "=>" in line:
                        try:
                            dll_path = line.split("=>", 1)[1].split("(", 1)[0].strip()
                            name = Path(dll_path).name
                            if name.lower().endswith(".dll"):
                                dlls.add(name)
                        except Exception:
                            continue
            except Exception:
                pass

        # Fallback + common runtime libs
        dlls.update([
            "avcodec-62.dll",
            "avformat-62.dll",
            "avutil-60.dll",
            "SDL2.dll",
            "swresample-6.dll",
            "libusb-1.0.dll",
            "libstdc++-6.dll",
            "libgcc_s_seh-1.dll",
            "libwinpthread-1.dll",
        ])

        copied = 0
        for name in sorted(dlls):
            src = dll_src / name
            if src.exists():
                try:
                    shutil.copy2(src, scrcpy_bin.parent / name)
                    copied += 1
                except Exception:
                    pass
        if copied:
            self.log_sys(f"Scrcpy runtime DLLs copied: {copied}")

    def on_scrcpy_window_toggle(self) -> None:
        if self.video_thread and isinstance(self.video_thread, ScrcpyVideoSource):
            self.log_sys("Scrcpy window toggle changed; restarting stream")
            self.toggle_live()
            self.toggle_live()

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
        self.device_states = {}
        for d in devs:
            state = d.get("state") or "unknown"
            label = f"{d['model']} ({d['serial']})"
            if state and state != "device":
                label += f" [{state}]"
            self.combo_dev.addItem(label, d['serial'])
            self.device_states[d['serial']] = state
            AdbManager.record_device(d['serial'], d['model'])
        self.combo_dev.blockSignals(False)
        if devs:
            online_idx = next((i for i, d in enumerate(devs) if d.get("state") == "device"), None)
            if online_idx is not None:
                self.on_dev_change(online_idx)
        self.update_history_combo()
        self.log_sys(f"Devices refreshed: {len(devs)} found")

    def on_dev_change(self, idx):
        self.active_device = self.combo_dev.itemData(idx)
        if self.active_device:
            self._root_prompted = False
            state = getattr(self, "device_states", {}).get(self.active_device, "device")
            if state != "device":
                self.log_sys(f"Selected device state is '{state}'. Reconnect or authorize the device.")
                return
            self.log_sys(f"Active device set: {self.active_device}")
            self.log_device_info()
            self.update_display_combo()

    def toggle_live(self):
        if self.video_thread:
            # Stop
            self.video_thread.stop_stream(); self.video_thread = None
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
            target_fps = 4 if self.perf_mode else 8
            source_text = self.combo_live_source.currentText() if hasattr(self, "combo_live_source") else "Scrcpy (fast)"
            if "Scrcpy" in source_text:
                self.scrcpy_path = self.resolve_scrcpy_path()
                if not self.scrcpy_path:
                    QMessageBox.warning(
                        self,
                        "Scrcpy not found",
                        "scrcpy.exe was not found. Build scrcpy in the local scrcpy-3.3.4 repo or set the path to your scrcpy 3.3.4 binary.",
                    )
                    return
                if self.chk_scrcpy_auto.isChecked():
                    self.update_scrcpy_repo()
                scrcpy_fps = 20 if self.perf_mode else 30
                scrcpy_server = self.find_scrcpy_server(self.scrcpy_path)
                self.video_thread = ScrcpyVideoSource(
                    self.active_device,
                    max_size=self.stream_max_size,
                    max_fps=scrcpy_fps,
                    bitrate=2_000_000,
                    scrcpy_path=self.scrcpy_path or None,
                    hide_window=(not self.chk_scrcpy_hide.isChecked()) if hasattr(self, "chk_scrcpy_hide") else True,
                    prefer_raw=self.chk_scrcpy_raw.isChecked() if hasattr(self, "chk_scrcpy_raw") else True,
                    display_id=self.selected_display_id,
                    server_path=scrcpy_server or None,
                )
                self.video_thread.log_line.connect(self.log_sys)
                self.log_sys(f"Live source: Scrcpy (fast) | bin: {self.scrcpy_path}")
                if scrcpy_server:
                    self.log_sys(f"Scrcpy server: {scrcpy_server}")
                self.log_sys(
                    "Scrcpy settings: "
                    f"max_size={self.stream_max_size or 'native'} "
                    f"fps={scrcpy_fps} bitrate=2000000 "
                    f"window={'shown' if self.chk_scrcpy_hide.isChecked() else 'hidden'} "
                    f"raw={'on' if self.chk_scrcpy_raw.isChecked() else 'off'}"
                )
                self.log_sys("Scrcpy output will appear below as it connects...")
            else:
                self.video_thread = VideoThread(self.active_device, target_fps=target_fps)
                self.log_sys("Live source: ADB (compat)")
            self.video_thread.frame_ready.connect(self.on_frame)
            self.video_thread.start_stream()
            
            self.xml_thread = HierarchyThread(self.active_device)
            self.xml_thread.tree_ready.connect(self.on_tree_data)
            self.xml_thread.dump_error.connect(self.on_dump_error)
            self.xml_thread.start()
            
            self.log_thread = LogcatThread(self.active_device)
            self.log_thread.log_line.connect(lambda l: self.txt_log.append(l))
            self.log_thread.start()
            
            self.focus_thread = FocusMonitorThread(self.active_device)
            self.focus_thread.focus_changed.connect(self.on_focus_changed)
            self.focus_thread.start()
            
            self.view.control_enabled = True
            self.btn_live.setText("STOP LIVE"); self.btn_live.setProperty("class", "danger")
            self.log_sys(f"Live mirror started on {self.active_device}")
            if hasattr(self.video_thread, "target_fps"):
                self.log_sys(f"Live capture target FPS: {self.video_thread.target_fps}")
            self.log_device_info()
        
        self.polish_btn(self.btn_live)

    def polish_btn(self, btn): btn.style().unpolish(btn); btn.style().polish(btn)

    def on_frame(self, data):
        if isinstance(data, QImage):
            img = data
        else:
            img = QImage.fromData(data)
        if img.isNull():
            return
        self.last_frame_image = img.copy()
        orig_w = img.width()
        orig_h = img.height()
        if self.stream_max_size:
            if max(img.width(), img.height()) > self.stream_max_size:
                img = img.scaled(
                    self.stream_max_size,
                    self.stream_max_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
        if orig_w > 0 and orig_h > 0:
            self.stream_scale = min(img.width() / orig_w, img.height() / orig_h)
        else:
            self.stream_scale = 1.0
        self.last_frame_size = (img.width(), img.height())
        if not self.pixmap_item:
            self.pixmap_item = self.scene.addPixmap(QPixmap.fromImage(img))
            self.pixmap_item.setZValue(0)
            self.handle_resize()
        else:
            self.pixmap_item.setPixmap(QPixmap.fromImage(img))
        if self.last_frame_size == (img.width(), img.height()):
            pass
        else:
            self.last_frame_size = (img.width(), img.height())
            self.log_sys(f"Live frame: {img.width()}x{img.height()} (dump bounds: {self.dump_bounds})")
        self.fps_counter += 1

    def update_fps(self):
        self.lbl_fps.setText(f"FPS: {self.fps_counter}")
        self.fps_counter = 0

    def log_device_info(self):
        if not self.active_device:
            return
        meta = AdbManager.get_device_meta(self.active_device)
        self.log_sys(f"Device model: {meta.get('model', 'Unknown')} | serial: {meta.get('serialno', 'n/a')}")
        size = AdbManager.get_screen_size(self.active_device)
        if size:
            self.device_bounds = (0, 0, size[0], size[1])
            self.log_sys(f"Display size: {size[0]}x{size[1]}")
        if not AdbManager.has_uiautomator_service(self.active_device):
            self.log_sys("⚠️ UIAutomator service not available on this device build. Live UI tree is unavailable.")
        ro_secure = meta.get("ro_secure", "unknown")
        if ro_secure in ("0", "1"):
            self.log_sys(f"Device security: ro.secure={ro_secure} ({'debug' if ro_secure == '0' else 'production'})")
        else:
            self.log_sys(f"Device security: ro.secure={ro_secure}")
        power = meta.get("power", {})
        self.log_sys(f"Power: wakefulness={power.get('wakefulness')} interactive={power.get('interactive')}")
        display_ids = meta.get("display_ids", [])
        if display_ids:
            self.log_sys(f"SurfaceFlinger displays: {', '.join(display_ids)}")
        display_info = meta.get("display_info", [])
        if display_info:
            self.log_sys(f"Display info count: {len(display_info)}")
        preferred = meta.get("preferred_display_id")
        if preferred:
            self.log_sys(f"Preferred display: {preferred}")

    def update_display_combo(self) -> None:
        if not hasattr(self, "combo_display"):
            return
        self.combo_display.blockSignals(True)
        self.combo_display.clear()
        self.combo_display.addItem("Auto (best)", None)
        if not self.active_device:
            self.combo_display.blockSignals(False)
            return

        details = AdbManager.get_display_details(self.active_device)
        display_ids = AdbManager.get_display_ids(self.active_device)
        if details:
            for item in details:
                disp_id = item.get("id")
                label = f"Display {disp_id}"
                extra = item.get("label") or ""
                size_match = re.search(r"(\d+) x (\d+)", extra)
                if size_match:
                    label += f" ({size_match.group(1)}x{size_match.group(2)})"
                elif extra:
                    label += f" - {extra}"
                self.combo_display.addItem(label, disp_id)
        else:
            for disp_id in display_ids:
                self.combo_display.addItem(f"Display {disp_id}", disp_id)

        if len(display_ids) > 1:
            self.log_sys(f"Multiple displays detected: {', '.join(display_ids)}. Use Display selector to switch.")

        self.combo_display.blockSignals(False)

    def on_display_change(self, idx: int) -> None:
        if not self.active_device:
            return
        display_id = self.combo_display.itemData(idx)
        self.selected_display_id = display_id
        AdbManager.set_preferred_display_id(self.active_device, display_id)
        if display_id:
            self.log_sys(f"Display set to {display_id} for live capture and dumps")
        else:
            self.log_sys("Display set to Auto (best match)")
        if self.video_thread and isinstance(self.video_thread, ScrcpyVideoSource):
            self.log_sys("Display change: restarting live mirror to apply display selection")
            self.toggle_live()
            self.toggle_live()

    def wake_screen(self) -> None:
        if not self.active_device:
            self.log_sys("Wake screen: no active device selected")
            return
        AdbManager.shell(self.active_device, ["input", "keyevent", "224"], timeout=3)
        AdbManager.shell(self.active_device, ["input", "keyevent", "82"], timeout=3)
        self.log_sys("Wake screen: sent WAKEUP + MENU (attempt unlock). If scrcpy was black, it should recover.")
        if self.video_thread and isinstance(self.video_thread, ScrcpyVideoSource):
            self.log_sys("Wake screen: restarting live mirror to refresh scrcpy capture")
            self.toggle_live()
            self.toggle_live()

    def sleep_screen(self) -> None:
        if not self.active_device:
            self.log_sys("Sleep screen: no active device selected")
            return
        AdbManager.shell(self.active_device, ["input", "keyevent", "223"], timeout=3)
        self.log_sys("Sleep screen: sent SLEEP. Scrcpy will go black until the screen is on.")

    def toggle_stay_awake(self) -> None:
        if not self.active_device:
            self.log_sys("Keep awake: no active device selected")
            return
        enabled = self.chk_stay_awake.isChecked()
        val = "true" if enabled else "false"
        AdbManager.shell(self.active_device, ["svc", "power", "stayon", val], timeout=3)
        state = "enabled" if enabled else "disabled"
        self.log_sys(f"Keep awake: {state} (screen stays on while USB power is connected).")
        self.log_secure_layers()

    def log_secure_layers(self) -> None:
        if not self.active_device:
            return
        layers = AdbManager.get_surfaceflinger_layers(self.active_device)
        if not layers:
            self.log_sys("SurfaceFlinger layers: unavailable")
            return
        secure_layers = [l for l in layers if l.get("secure")]
        if secure_layers:
            self.log_sys(f"⚠️ Secure layers detected: {len(secure_layers)} (UI dumps may be incomplete)")
            for l in secure_layers[:8]:
                self.log_sys(f"  - {l.get('name')}")
            if len(secure_layers) > 8:
                self.log_sys(f"  - ...and {len(secure_layers) - 8} more")
        else:
            self.log_sys("SurfaceFlinger layers: no secure layers detected")

    def on_tree_data(self, xml_str, changed):
        if not changed and self.root_node: return

        if self.perf_mode and self.video_thread:
            now = time.time()
            if now - self.last_tree_update < 1.5:
                return
            self.last_tree_update = now
        
        root, parse_err = UixParser.parse(xml_str)
        self.root_node = root
        if root and root.valid_bounds:
            self.dump_bounds = root.rect
        else:
            self.dump_bounds = None
        
        self.tree.clear(); self.current_node_map = {}; self.node_to_item_map = {}; self.rect_map = []
        if root:
            self.populate_tree(root, self.tree)
            node_count = self.count_nodes(root)
            self.log_sys(f"UI tree updated: {node_count} nodes")
            if parse_err:
                self.log_sys("UI dump loaded but has zero valid bounds. The dump may be incomplete.")
                self.set_tree_status("Partial", "#d9a441")
            elif not self.rect_map:
                self.set_tree_status("Partial", "#d9a441")
            else:
                self.set_tree_status("OK", "#69d08f")
        else:
            self.log_sys("UI dump parsed with no nodes. The dump may be invalid.")
            self.set_tree_placeholder("UI dump unavailable", "No valid nodes found in the dump.")
            self.rect_item.hide()
            self.set_tree_status("Unavailable", "#e06b6b")

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

    def set_tree_placeholder(self, title: str, detail: str = "") -> None:
        self.tree.clear()
        self.current_node_map = {}
        self.node_to_item_map = {}
        self.rect_map = []
        root_item = QTreeWidgetItem(self.tree)
        root_item.setText(0, title)
        if detail:
            detail_item = QTreeWidgetItem(root_item)
            detail_item.setText(0, detail)
        self.tree.expandAll()

    def count_nodes(self, node) -> int:
        if not node:
            return 0
        total = 1
        for child in node.children:
            total += self.count_nodes(child)
        return total

    def on_mouse_hover(self, x, y):
        self.lbl_coords.setText(f"X: {x}, Y: {y}")
        # Hover detection
        best_node = None; best_area = float('inf')
        sx, sy, ox, oy = self.get_bounds_transform()
        for rect, node in self.rect_map:
            rx, ry, rw, rh = self.scale_rect(rect, sx, sy, ox, oy)
            if rx <= x <= rx+rw and ry <= y <= ry+rh:
                area = rw * rh
                if area < best_area: best_area = area; best_node = node
        
        if best_node:
            self.view.setCursor(Qt.PointingHandCursor if best_node.clickable else Qt.ArrowCursor)
            if self.auto_follow_hover and not self.locked_node:
                self.select_node(best_node, scroll=True)

    def handle_tap(self, x, y):
        # Always log the tap coordinate to help users who need manual test coordinates (System UI workaround)
        if self.video_thread:
            dx, dy = self.to_device_coords(x, y)
            # Log as raw coords AND as a copy-pasteable Java snippet
            self.log_sys(f"👆 Tap({int(dx)}, {int(dy)})")
            self.log_sys(f"   📋 Java: clickSystemCoordinate({int(dx)}, {int(dy)});")
            
            AdbManager.tap(self.active_device, dx, dy)
            self.request_tree_refresh()
        else:
            # Lock selection in offline mode
            node = self.find_node_at(x, y)
            if node:
                self.toggle_lock(node)

    def handle_swipe(self, x1, y1, x2, y2):
        if self.video_thread:
            dx1, dy1 = self.to_device_coords(x1, y1)
            dx2, dy2 = self.to_device_coords(x2, y2)
            self.log_sys(f"👆 Swipe Input: ({int(dx1)}, {int(dy1)}) -> ({int(dx2)}, {int(dy2)})")
            AdbManager.swipe(self.active_device, dx1, dy1, dx2, dy2)
            self.request_tree_refresh()

    def select_node(self, node, scroll=True):
        sx, sy, ox, oy = self.get_bounds_transform()
        x, y, w, h = self.scale_rect(node.rect, sx, sy, ox, oy)
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
            if self.last_frame_image and not self.last_frame_image.isNull():
                self.last_frame_image.save(os.path.join(path, "screenshot.png"), "PNG")
                self.log_sys("Snapshot image saved from live frame cache")
            else:
                self.log_sys("Snapshot image saved from ADB screencap")
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
            self.stream_scale = 1.0
            px = self.pixmap_item.pixmap()
            if not px.isNull():
                self.last_frame_size = (px.width(), px.height())
            else:
                self.last_frame_size = None
            
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

    def set_adb_server(self) -> None:
        raw = self.input_adb_server.text().strip()
        if not raw:
            AdbManager.clear_adb_server()
            self.log_sys("ADB server reset to local")
            self.refresh_devices()
            return
        if ":" in raw:
            host, port_str = raw.split(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                self.log_sys("ADB server format invalid (expected host:port)")
                return
        else:
            host = raw
            port = 5037
        AdbManager.set_adb_server(host, port)
        self.log_sys(f"ADB server set to {host}:{port}")
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
            if self.video_thread and isinstance(self.video_thread, ScrcpyVideoSource):
                self.log_sys("Scrcpy size changed; restarting stream")
                self.toggle_live()
                self.toggle_live()
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
        if self.video_thread and isinstance(self.video_thread, ScrcpyVideoSource):
            self.log_sys("Scrcpy size changed; restarting stream")
            self.toggle_live()
            self.toggle_live()

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

    def closeEvent(self, event):
        if self.video_thread:
            self.toggle_live()
        super().closeEvent(event)

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
        sx, sy, ox, oy = self.get_bounds_transform()
        for rect, node in self.rect_map:
            rx, ry, rw, rh = self.scale_rect(rect, sx, sy, ox, oy)
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                area = rw * rh
                if area < best_area:
                    best_area = area
                    best_node = node
        return best_node

    def get_bounds_transform(self):
        if self.dump_bounds and self.last_frame_size:
            ox, oy, ow, oh = self.dump_bounds
            fw, fh = self.last_frame_size
            if ow > 0 and oh > 0 and fw > 0 and fh > 0:
                return (fw / ow, fh / oh, ox, oy)
        if self.device_bounds and self.last_frame_size:
            ox, oy, ow, oh = self.device_bounds
            fw, fh = self.last_frame_size
            if ow > 0 and oh > 0 and fw > 0 and fh > 0:
                return (fw / ow, fh / oh, ox, oy)
        return (1.0, 1.0, 0.0, 0.0)

    def scale_rect(self, rect, sx: float, sy: float, ox: float, oy: float):
        rx, ry, rw, rh = rect
        return ((rx - ox) * sx, (ry - oy) * sy, rw * sx, rh * sy)

    def to_device_coords(self, x: int, y: int):
        sx, sy, ox, oy = self.get_bounds_transform()
        if sx <= 0 or sy <= 0:
            return x, y
        return int(x / sx + ox), int(y / sy + oy)

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

    def on_focus_changed(self, focus: str) -> None:
        self.lbl_focus.setText(f"Focus: {focus}")
        self.request_tree_refresh("Focus changed", log=True)

    def set_tree_status(self, status: str, color: str = "#9aa7bd") -> None:
        if hasattr(self, "lbl_tree_status") and self.lbl_tree_status:
            self.lbl_tree_status.setText(f"Tree: {status}")
            self.lbl_tree_status.setStyleSheet(f"color: {color}; font-weight: 600;")

    def on_dump_error(self, msg: str) -> None:
        self.log_sys(msg)
        lower_msg = msg.lower()
        if "existing /sdcard/window_dump.xml" in lower_msg:
            self.set_tree_status("Stale", "#d9a441")
        else:
            self.set_tree_status("Unavailable", "#e06b6b")
        if "service not available" in msg.lower():
            self.log_sys("This device build does not expose UIAutomator. Ask OEM/firmware team to enable it or use offline dumps.")
        if "killed" in msg.lower():
            self.log_sys("UI dump is being killed by the device. Live tree and hover will be unavailable until a dump succeeds.")
            self.log_sys("Try: keep the device unlocked, close heavy apps, or switch Display to Auto. You can still capture offline snapshots.")
        if self.active_device and not self._root_prompted:
            should_prompt = (
                "killed" in lower_msg
                or "uiautomator dump failed" in lower_msg
                or "service not available" in lower_msg
            )
            if should_prompt and not AdbManager.is_adb_root(self.active_device):
                self._root_prompted = True
                resp = QMessageBox.question(
                    self,
                    "ADB root required",
                    "UI dump failed. This device may require adb root to access UIAutomator.\n\n"
                    "Run 'adb root' now? (adbd will restart)",
                )
                if resp == QMessageBox.Yes:
                    ok, out = AdbManager.adb_root(self.active_device)
                    self.log_sys(out or "adb root attempted")
                    if ok:
                        self.log_sys("adb root succeeded; refreshing UI tree...")
                        self.request_tree_refresh("adb root", log=True)
                else:
                    self.log_sys("adb root skipped by user")
        if not self.root_node:
            self.set_tree_placeholder("UI dump unavailable", msg)

    def request_tree_refresh(self, reason: str = "", log: bool = False) -> None:
        if self.xml_thread and hasattr(self.xml_thread, "request_refresh"):
            self.xml_thread.request_refresh()
            if log and reason:
                self.log_sys(f"UI tree refresh requested: {reason}")

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
        if self.video_thread:
            if isinstance(self.video_thread, ScrcpyVideoSource):
                self.video_thread.set_target_fps(20 if self.perf_mode else 30)
            else:
                self.video_thread.set_target_fps(4 if self.perf_mode else 8)
            self.log_sys(f"Live capture target FPS: {self.video_thread.target_fps}")
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
