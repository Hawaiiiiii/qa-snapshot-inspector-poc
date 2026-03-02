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
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QFileDialog, QTextEdit,
    QGroupBox, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QToolBar, QTabWidget, QStatusBar, QFrame, QDockWidget, QApplication, QLineEdit, QCheckBox, QMessageBox,
    QMenu, QToolButton, QScrollArea, QAbstractItemView
)
from PySide6.QtGui import QPixmap, QPen, QBrush, QImage, QColor, QAction, QPainter, QCursor, QLinearGradient, QPalette, QGuiApplication
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
from PySide6.QtCore import Qt, QRectF, Signal, QTimer

from qa_snapshot_tool.utils import get_app_root
from qa_snapshot_tool.uix_parser import UixParser
from qa_snapshot_tool.locator_suggester import LocatorSuggester
from qa_snapshot_tool.adb_manager import AdbManager
from qa_snapshot_tool.live_mirror import VideoThread, ScrcpyVideoSource, HierarchyThread, LogcatThread, FocusMonitorThread
from qa_snapshot_tool.theme import Theme
from qa_snapshot_tool.settings import AppSettings
from qa_snapshot_tool.device_profiles import detect_capabilities
from qa_snapshot_tool.session_recorder import SessionRecorder
from qa_snapshot_tool.maestro_handoff import export_session_handoff
from qa_snapshot_tool.perf_metrics import PerfTracker
from qa_snapshot_native import backend_name as native_backend_name, smallest_hit, sort_rects_by_area


@dataclass
class DeviceWorkspace:
    serial: str
    model: str = "Unknown"
    selected_display_id: Optional[str] = None
    video_thread: Optional[Any] = None
    xml_thread: Optional[HierarchyThread] = None
    log_thread: Optional[LogcatThread] = None
    focus_thread: Optional[FocusMonitorThread] = None
    recorder: Optional[SessionRecorder] = None
    last_frame_image: Optional[QImage] = None
    last_frame_size: Optional[tuple[int, int]] = None
    stream_scale: float = 1.0
    dump_bounds: Optional[tuple[int, int, int, int]] = None
    device_bounds: Optional[tuple[int, int, int, int]] = None
    last_xml: str = ""
    log_lines: List[str] = field(default_factory=list)
    focus_text: str = "-"
    last_snapshot_path: Optional[str] = None
    last_handoff_manifest: Optional[str] = None
    environment_type: str = "rack"
    profile: str = "rack_aaos"

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

        self.settings = AppSettings.load()
        self.workspaces: Dict[str, DeviceWorkspace] = {}
        self.workspace_serials: List[str] = []
        self.active_workspace_serial: Optional[str] = None
        self.perf = PerfTracker()
        self.last_hover_ts = 0.0
        self.rect_map_sorted = []
        self.timeline_event_file_paths: Dict[int, str] = {}
        self.timeline_event_payloads: Dict[int, str] = {}

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
        self.ambient_enabled = False
        self.ambient_phase = 0.0
        self.ambient_offset = 0.0
        self.ambient_widgets = []
        self.ambient_panels = []
        self.ambient_player = None
        self.ambient_audio = None
        self.ambient_sink = None
        self.ambient_last_hash = None
        self.ambient_prev_image = None
        self.ambient_last_frame_ts = 0.0
        self.ambient_frame_interval_ms = 90
        self.ambient_static_frame = None
        self.perf_mode = False
        self.last_tree_update = 0.0
        self.last_snapshot_path = None
        self.last_handoff_manifest = None
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
        scrcpy_root = get_app_root() / "scrcpy-3.3.4"
        scrcpy_git_repo = scrcpy_root / "scrcpy-git"
        scrcpy_snapshot_repo = scrcpy_root / "scrcpy-3.3.4"
        self.scrcpy_repo_path = str(scrcpy_git_repo if (scrcpy_git_repo / ".git").exists() else scrcpy_snapshot_repo)
        self.prefer_raw_scrcpy = True
        self._initial_resize_done = False
        self.syslog_auto_scroll = True
        
        self.setup_ui()
        self.refresh_devices()
        self.refresh_timeline_sessions()
        self.log_sys(f"Hotspot backend active: {native_backend_name()}")

        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)

        self.ambient_timer = QTimer()
        self.ambient_timer.timeout.connect(self.update_ambient)

    def showEvent(self, event):
        super().showEvent(event)
        if self._initial_resize_done:
            return
        screen = QGuiApplication.primaryScreen()
        if not screen:
            self._initial_resize_done = True
            return
        available = screen.availableGeometry()
        target_w = max(1200, int(available.width() * 0.95))
        target_h = max(800, int(available.height() * 0.95))
        target_w = min(target_w, available.width())
        target_h = min(target_h, available.height())
        self.resize(target_w, target_h)
        self.move(available.left(), available.top())
        self._initial_resize_done = True

    def center_window(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        target_x = available.left() + max(0, (available.width() - frame.width()) // 2)
        target_y = available.top() + max(0, (available.height() - frame.height()) // 2)
        self.move(target_x, target_y)

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
        self.lbl_perf = QLabel("Perf: -"); self.lbl_perf.setStyleSheet("color: #9aa7bd; font-weight: 600;")
        self.lbl_native = QLabel(f"Hotspot: {native_backend_name()}"); self.lbl_native.setStyleSheet("color: #9aa7bd; font-weight: 600;")
        
        act_fit = QAction("Fit Screen", self); act_fit.triggered.connect(self.enable_fit)
        act_11 = QAction("1:1 Pixel", self); act_11.triggered.connect(self.disable_fit)
        act_center = QAction("Center Window", self); act_center.triggered.connect(self.center_window)
        
        tb.addWidget(self.lbl_fps); tb.addWidget(self.lbl_coords); tb.addSeparator(); tb.addWidget(self.lbl_focus)
        tb.addSeparator(); tb.addWidget(self.lbl_tree_status); tb.addSeparator(); tb.addWidget(self.lbl_perf); tb.addWidget(self.lbl_native)
        tb.addSeparator(); tb.addAction(act_fit); tb.addAction(act_11); tb.addAction(act_center)

        self.panels_menu = QMenu("Panels", self)
        self.menuBar().addMenu(self.panels_menu)
        panels_button = QToolButton()
        panels_button.setText("Panels")
        panels_button.setMenu(self.panels_menu)
        panels_button.setPopupMode(QToolButton.InstantPopup)
        tb.addSeparator(); tb.addWidget(panels_button)
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

        for dock in (self.dock_env, self.dock_tree, self.dock_inspector, self.dock_syslog):
            dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
            self.panels_menu.addAction(dock.toggleViewAction())

        if self.ambient_enabled:
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

        ws_row = QHBoxLayout()
        self.btn_add_workspace = QPushButton("Add Workspace")
        self.btn_add_workspace.clicked.connect(self.add_current_workspace)
        self.btn_remove_workspace = QPushButton("Remove Workspace")
        self.btn_remove_workspace.clicked.connect(self.remove_active_workspace)
        ws_row.addWidget(self.btn_add_workspace)
        ws_row.addWidget(self.btn_remove_workspace)

        self.tabs_workspace = QTabWidget()
        self.tabs_workspace.setDocumentMode(True)
        self.tabs_workspace.currentChanged.connect(self.on_workspace_tab_changed)
        self.tabs_workspace.setToolTip("Device workspaces (up to 3 concurrent live sessions).")

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
        gl.addLayout(ws_row)
        gl.addWidget(self.tabs_workspace)
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

        self.chk_emulator_beta = QCheckBox("Enable emulator beta support")
        self.chk_emulator_beta.setChecked(self.settings.emulator_beta_enabled)
        self.chk_emulator_beta.stateChanged.connect(self.toggle_emulator_beta)
        self.chk_emulator_beta.setToolTip("Rack-first policy: emulator support is explicit beta.")

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

        ll.addWidget(self.btn_live); ll.addWidget(self.chk_turbo); ll.addLayout(src_row); ll.addWidget(self.chk_emulator_beta); ll.addLayout(scrcpy_row)
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

        maestro_row = QHBoxLayout()
        self.input_maestro_workspace = QLineEdit()
        self.input_maestro_workspace.setPlaceholderText("Maestro workspace path")
        self.input_maestro_workspace.setText(self.settings.maestro_workspace_path)
        self.input_maestro_workspace.editingFinished.connect(self.save_maestro_workspace)
        self.btn_maestro_browse = QPushButton("Browse")
        self.btn_maestro_browse.clicked.connect(self.browse_maestro_workspace)
        maestro_row.addWidget(self.input_maestro_workspace)
        maestro_row.addWidget(self.btn_maestro_browse)

        self.btn_export_handoff = QPushButton("Export To Maestro")
        self.btn_export_handoff.clicked.connect(self.export_active_session_to_maestro)
        self.btn_open_handoff = QPushButton("Open Handoff Folder")
        self.btn_open_handoff.clicked.connect(self.open_last_handoff_folder)
        self.btn_copy_handoff = QPushButton("Copy Manifest Path")
        self.btn_copy_handoff.clicked.connect(self.copy_last_handoff_manifest)
        self.btn_open_maestro_flows = QPushButton("Open Maestro Flows")
        self.btn_open_maestro_flows.clicked.connect(self.open_maestro_flows)

        sl.addWidget(btn_cap); sl.addWidget(btn_load); sl.addWidget(self.btn_recapture)
        sl.addLayout(maestro_row)
        sl.addWidget(self.btn_export_handoff)
        sl.addWidget(self.btn_open_handoff)
        sl.addWidget(self.btn_copy_handoff)
        sl.addWidget(self.btn_open_maestro_flows)
        gb_snap.setLayout(sl); l.addWidget(gb_snap)

        gb_opts = QGroupBox("UX Options"); ol = QVBoxLayout()
        self.chk_auto_follow = QCheckBox("Auto Locate Hover")
        self.chk_auto_follow.setChecked(True)
        self.chk_auto_follow.stateChanged.connect(self.toggle_auto_follow)
        self.chk_auto_follow.setToolTip("Auto-scroll the UI Tree to the element under the cursor.")

        self.chk_ambient = QCheckBox("Ambient Video")
        self.chk_ambient.setChecked(False)
        self.chk_ambient.stateChanged.connect(self.toggle_ambient_video)
        self.chk_ambient.setToolTip("Animate the dock panels only. Live view stays clean.")

        self.chk_perf = QCheckBox("Performance Mode")
        self.chk_perf.setChecked(False)
        self.chk_perf.stateChanged.connect(self.toggle_perf_mode)
        self.chk_perf.setToolTip("Reduce UI tree refresh rate while live streaming.")

        ol.addWidget(self.chk_auto_follow); ol.addWidget(self.chk_ambient); ol.addWidget(self.chk_perf)
        gb_opts.setLayout(ol); l.addWidget(gb_opts)
        
        l.addStretch()
        scroll = self.wrap_scroll_area(w)
        d.setWidget(self.wrap_ambient_panel(scroll)); self.addDockWidget(Qt.LeftDockWidgetArea, d)
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
        self.tbl_props.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tbl_props.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tbl_props.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tbl_props.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
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

        # Timeline / Evidence Tab
        w_timeline = QWidget(); l_timeline = QVBoxLayout(w_timeline)
        timeline_top = QHBoxLayout()
        self.combo_timeline_session = QComboBox()
        self.combo_timeline_session.setToolTip("Recorded live sessions from the local session store.")
        self.btn_timeline_refresh = QPushButton("Refresh")
        self.btn_timeline_refresh.clicked.connect(self.refresh_timeline_sessions)
        self.btn_timeline_load = QPushButton("Load")
        self.btn_timeline_load.clicked.connect(self.load_selected_timeline_session)
        self.btn_timeline_open = QPushButton("Open Folder")
        self.btn_timeline_open.clicked.connect(self.open_selected_timeline_session)
        timeline_top.addWidget(self.combo_timeline_session)
        timeline_top.addWidget(self.btn_timeline_refresh)
        timeline_top.addWidget(self.btn_timeline_load)
        timeline_top.addWidget(self.btn_timeline_open)

        self.tbl_timeline = QTableWidget()
        self.tbl_timeline.setColumnCount(4)
        self.tbl_timeline.setHorizontalHeaderLabels(["Time", "Type", "File", "Payload"])
        self.tbl_timeline.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_timeline.verticalHeader().setVisible(False)
        self.tbl_timeline.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_timeline.itemSelectionChanged.connect(self.on_timeline_selection_changed)

        timeline_actions = QHBoxLayout()
        self.btn_timeline_open_file = QPushButton("Open Event File")
        self.btn_timeline_open_file.clicked.connect(self.open_selected_timeline_file)
        self.btn_timeline_export = QPushButton("Export Session To Maestro")
        self.btn_timeline_export.clicked.connect(self.export_selected_timeline_to_maestro)
        timeline_actions.addWidget(self.btn_timeline_open_file)
        timeline_actions.addWidget(self.btn_timeline_export)

        self.txt_timeline_detail = QTextEdit(); self.txt_timeline_detail.setReadOnly(True)
        self.txt_timeline_detail.setToolTip("Selected timeline event details.")

        l_timeline.addLayout(timeline_top)
        l_timeline.addWidget(self.tbl_timeline)
        l_timeline.addLayout(timeline_actions)
        l_timeline.addWidget(self.txt_timeline_detail)
        tabs.addTab(w_timeline, "Timeline")

        d.setWidget(self.wrap_ambient_panel(tabs)); self.addDockWidget(Qt.BottomDockWidgetArea, d)

    def setup_syslog_dock(self):
        d = QDockWidget("System Log", self)
        self.dock_syslog = d
        self.register_ambient_widget(d)
        self.txt_sys = QTextEdit(); self.txt_sys.setReadOnly(True)
        self.txt_sys.setToolTip("Internal app events, status updates, and diagnostics.")
        self.txt_sys.verticalScrollBar().valueChanged.connect(self.on_syslog_scroll)
        d.setWidget(self.wrap_ambient_panel(self.txt_sys)); self.addDockWidget(Qt.BottomDockWidgetArea, d)

    # --- Core Logic ---

    def log_sys(self, message: str) -> None:
        if not hasattr(self, "txt_sys"):
            return
        ts = time.strftime("%H:%M:%S")
        self.txt_sys.append(f"[{ts}] {message}")
        if self.syslog_auto_scroll:
            bar = self.txt_sys.verticalScrollBar()
            bar.setValue(bar.maximum())

    def on_syslog_scroll(self, value: int) -> None:
        bar = self.txt_sys.verticalScrollBar()
        self.syslog_auto_scroll = value >= bar.maximum()

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
            scrcpy_root = get_app_root() / "scrcpy-3.3.4"
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

    def wrap_scroll_area(self, widget: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        area.setWidget(widget)
        return area

    def init_ambient_video(self) -> None:
        root = get_app_root()
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

    def _workspace_label(self, workspace: DeviceWorkspace) -> str:
        live = bool(workspace.video_thread)
        mark = "●" if live else "○"
        return f"{mark} {workspace.model} ({workspace.serial})"

    def _active_workspace(self) -> Optional[DeviceWorkspace]:
        if not self.active_workspace_serial:
            return None
        return self.workspaces.get(self.active_workspace_serial)

    def ensure_workspace(self, serial: str, model: str = "Unknown") -> Optional[DeviceWorkspace]:
        serial = (serial or "").strip()
        if not serial:
            return None
        if serial in self.workspaces:
            ws = self.workspaces[serial]
            if model and model != "Unknown":
                ws.model = model
            return ws
        if len(self.workspaces) >= self.settings.max_concurrent_devices:
            self.log_sys(f"Workspace limit reached ({self.settings.max_concurrent_devices}). Remove one before adding another.")
            return None
        ws = DeviceWorkspace(serial=serial, model=model or "Unknown")
        self.workspaces[serial] = ws
        self.workspace_serials.append(serial)
        self._refresh_workspace_tabs()
        return ws

    def _refresh_workspace_tabs(self) -> None:
        if not hasattr(self, "tabs_workspace"):
            return
        current = self.active_workspace_serial
        self.tabs_workspace.blockSignals(True)
        self.tabs_workspace.clear()
        for serial in self.workspace_serials:
            ws = self.workspaces.get(serial)
            if not ws:
                continue
            tab_widget = QWidget()
            self.tabs_workspace.addTab(tab_widget, self._workspace_label(ws))
        if current and current in self.workspace_serials:
            idx = self.workspace_serials.index(current)
            self.tabs_workspace.setCurrentIndex(idx)
        self.tabs_workspace.blockSignals(False)

    def on_workspace_tab_changed(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.workspace_serials):
            return
        serial = self.workspace_serials[idx]
        self.set_active_workspace(serial)

    def add_current_workspace(self) -> None:
        idx = self.combo_dev.currentIndex()
        serial = self.combo_dev.itemData(idx)
        if not serial:
            return
        label = self.combo_dev.currentText()
        model = label.split(" (", 1)[0] if label else "Unknown"
        ws = self.ensure_workspace(serial, model=model)
        if ws:
            self.set_active_workspace(serial)

    def remove_active_workspace(self) -> None:
        ws = self._active_workspace()
        if not ws:
            return
        serial = ws.serial
        if ws.video_thread:
            self.stop_live_for_workspace(ws)
        self.workspaces.pop(serial, None)
        self.workspace_serials = [item for item in self.workspace_serials if item != serial]
        self.active_workspace_serial = None
        self.active_device = None
        self._refresh_workspace_tabs()
        if self.workspace_serials:
            self.set_active_workspace(self.workspace_serials[0])
        else:
            self.btn_live.setText("START LIVE STREAM")
            self.btn_live.setProperty("class", "primary")
            self.polish_btn(self.btn_live)
            self.txt_log.setText("")
            self.lbl_focus.setText("Focus: -")
            self.log_sys(f"Workspace removed: {serial}")

    def set_active_workspace(self, serial: str) -> None:
        if not serial or serial not in self.workspaces:
            return
        prev = self._active_workspace()
        if prev and prev.serial != serial:
            self._store_workspace_view_state(prev)

        self.active_workspace_serial = serial
        ws = self.workspaces[serial]
        self.active_device = serial
        self.selected_display_id = ws.selected_display_id
        AdbManager.set_preferred_display_id(serial, ws.selected_display_id)
        self.last_snapshot_path = ws.last_snapshot_path
        self.last_handoff_manifest = ws.last_handoff_manifest

        # Keep combo device selection synchronized with workspace selection.
        if hasattr(self, "combo_dev"):
            for idx in range(self.combo_dev.count()):
                if self.combo_dev.itemData(idx) == serial:
                    self.combo_dev.blockSignals(True)
                    self.combo_dev.setCurrentIndex(idx)
                    self.combo_dev.blockSignals(False)
                    break

        self._bind_active_workspace_threads()
        self._load_workspace_view_state(ws)
        self.update_display_combo()
        self._apply_background_scheduler()
        self._refresh_workspace_tabs()

    def _bind_active_workspace_threads(self) -> None:
        ws = self._active_workspace()
        self.video_thread = ws.video_thread if ws else None
        self.xml_thread = ws.xml_thread if ws else None
        self.log_thread = ws.log_thread if ws else None
        self.focus_thread = ws.focus_thread if ws else None
        live = bool(ws and ws.video_thread)
        self.btn_live.setText("STOP LIVE" if live else "START LIVE STREAM")
        self.btn_live.setProperty("class", "danger" if live else "primary")
        self.polish_btn(self.btn_live)

    def _store_workspace_view_state(self, ws: DeviceWorkspace) -> None:
        ws.last_frame_image = self.last_frame_image.copy() if self.last_frame_image and not self.last_frame_image.isNull() else ws.last_frame_image
        ws.last_frame_size = self.last_frame_size
        ws.stream_scale = self.stream_scale
        ws.dump_bounds = self.dump_bounds
        ws.device_bounds = self.device_bounds
        ws.last_snapshot_path = self.last_snapshot_path
        ws.last_handoff_manifest = self.last_handoff_manifest

    def _load_workspace_view_state(self, ws: DeviceWorkspace) -> None:
        self.last_frame_image = ws.last_frame_image.copy() if ws.last_frame_image and not ws.last_frame_image.isNull() else None
        self.last_frame_size = ws.last_frame_size
        self.stream_scale = ws.stream_scale if ws.stream_scale else 1.0
        self.dump_bounds = ws.dump_bounds
        self.device_bounds = ws.device_bounds

        if ws.last_frame_image and not ws.last_frame_image.isNull():
            self.on_frame(ws.last_frame_image)
        else:
            if self.pixmap_item:
                self.scene.removeItem(self.pixmap_item)
                self.pixmap_item = None
            self.rect_item.hide()

        if ws.last_xml:
            self.on_tree_data(ws.last_xml, True)
        else:
            self.tree.clear()
            self.current_node_map = {}
            self.node_to_item_map = {}
            self.rect_map = []
            self.tbl_props.setRowCount(0)

        self.txt_log.setText("\n".join(ws.log_lines[-5000:]))
        self.lbl_focus.setText(f"Focus: {ws.focus_text}")

    def _apply_background_scheduler(self) -> None:
        active_serial = self.active_workspace_serial
        for serial, ws in self.workspaces.items():
            if not ws.video_thread or not hasattr(ws.video_thread, "set_target_fps"):
                continue
            active = serial == active_serial
            if isinstance(ws.video_thread, ScrcpyVideoSource):
                target = 20 if self.perf_mode else 30
                bg = 8
            else:
                target = 4 if self.perf_mode else 8
                bg = 2
            ws.video_thread.set_target_fps(target if active else bg)

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
            if d.get("state") == "device":
                if d["serial"] in self.workspaces:
                    self.workspaces[d["serial"]].model = d.get("model", "Unknown")
        self.combo_dev.blockSignals(False)
        if devs:
            online_idx = next((i for i, d in enumerate(devs) if d.get("state") == "device"), None)
            if online_idx is not None:
                self.on_dev_change(online_idx)
        self._refresh_workspace_tabs()
        self.update_history_combo()
        self.log_sys(f"Devices refreshed: {len(devs)} found")

    def on_dev_change(self, idx):
        serial = self.combo_dev.itemData(idx)
        if serial:
            self._root_prompted = False
            state = getattr(self, "device_states", {}).get(serial, "device")
            if state != "device":
                self.log_sys(f"Selected device state is '{state}'. Reconnect or authorize the device.")
                return
            model = self.combo_dev.currentText().split(" (", 1)[0]
            ws = self.ensure_workspace(serial, model=model)
            if not ws:
                return
            self.set_active_workspace(serial)
            self.log_sys(f"Active device set: {serial}")
            self.log_device_info()

    def toggle_live(self):
        ws = self._active_workspace()
        if not ws:
            self.log_sys("Live mirror requested but no workspace is selected")
            return

        if ws.video_thread:
            self.stop_live_for_workspace(ws)
            self.log_sys(f"Live mirror stopped on {ws.serial}")
            self._bind_active_workspace_threads()
            self._apply_background_scheduler()
            self._refresh_workspace_tabs()
            return

        serial = ws.serial
        if not serial:
            self.log_sys("Live mirror requested but no device is selected")
            return

        caps = detect_capabilities(serial, emulator_beta_enabled=self.settings.emulator_beta_enabled)
        ws.environment_type = caps.environment_type
        ws.profile = caps.profile
        if caps.environment_type == "emulator" and not self.settings.emulator_beta_enabled:
            self.log_sys("Emulator detected. Enable 'emulator beta support' to start live capture on emulator targets.")
            return

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
            ws.video_thread = ScrcpyVideoSource(
                serial,
                max_size=self.stream_max_size,
                max_fps=scrcpy_fps,
                bitrate=2_000_000,
                scrcpy_path=self.scrcpy_path or None,
                hide_window=(not self.chk_scrcpy_hide.isChecked()) if hasattr(self, "chk_scrcpy_hide") else True,
                prefer_raw=self.chk_scrcpy_raw.isChecked() if hasattr(self, "chk_scrcpy_raw") else True,
                display_id=ws.selected_display_id,
                server_path=scrcpy_server or None,
            )
            ws.video_thread.log_line.connect(lambda line, s=serial: self.on_workspace_log_line(s, line, source="scrcpy"))
            self.log_sys(f"Live source: Scrcpy (fast) | {serial} | bin: {self.scrcpy_path}")
            if scrcpy_server:
                self.log_sys(f"Scrcpy server: {scrcpy_server}")
        else:
            ws.video_thread = VideoThread(serial, target_fps=target_fps)
            self.log_sys(f"Live source: ADB (compat) | {serial}")

        ws.video_thread.frame_ready.connect(lambda data, s=serial: self.on_workspace_frame(s, data))
        ws.video_thread.start_stream()

        ws.xml_thread = HierarchyThread(serial)
        ws.xml_thread.tree_ready.connect(lambda xml, changed, s=serial: self.on_workspace_tree(s, xml, changed))
        ws.xml_thread.dump_error.connect(lambda msg, s=serial: self.on_workspace_dump_error(s, msg))
        ws.xml_thread.start()

        ws.log_thread = LogcatThread(serial)
        ws.log_thread.log_line.connect(lambda line, s=serial: self.on_workspace_log_line(s, line, source="logcat"))
        ws.log_thread.start()

        ws.focus_thread = FocusMonitorThread(serial)
        ws.focus_thread.focus_changed.connect(lambda focus, s=serial: self.on_workspace_focus(s, focus))
        ws.focus_thread.start()

        if self.settings.auto_record_live:
            model = ws.model or "Unknown"
            try:
                meta = AdbManager.get_device_meta(serial)
                model = meta.get("model") or model
            except Exception:
                pass
            ws.recorder = SessionRecorder.start_session(
                session_root=self.settings.session_root_path(),
                serial=serial,
                model=model,
                environment_type=ws.environment_type,
                profile=ws.profile,
                display_id=ws.selected_display_id,
                session_max_bytes=self.settings.session_max_bytes,
            )
            ws.recorder.record_event("live_started", {"source": source_text})
            self.log_sys(f"Session recorder started: {ws.recorder.session_dir}")

        self.view.control_enabled = True
        self.log_sys(f"Live mirror started on {serial}")
        self._bind_active_workspace_threads()
        self._apply_background_scheduler()
        self._refresh_workspace_tabs()
        self.log_device_info()

    def stop_live_for_workspace(self, ws: DeviceWorkspace) -> None:
        if ws.video_thread:
            ws.video_thread.stop_stream()
            ws.video_thread = None
        if ws.xml_thread:
            ws.xml_thread.stop()
            ws.xml_thread = None
        if ws.log_thread:
            ws.log_thread.stop()
            ws.log_thread = None
        if ws.focus_thread:
            ws.focus_thread.stop()
            ws.focus_thread = None
        if ws.recorder:
            ws.recorder.record_event("live_stopped", {"serial": ws.serial})
            ws.recorder.finish_session("stopped")
            ws.recorder = None
            self.refresh_timeline_sessions()
        if ws.serial == self.active_workspace_serial:
            self.view.control_enabled = False

    def polish_btn(self, btn): btn.style().unpolish(btn); btn.style().polish(btn)

    def on_workspace_frame(self, serial: str, data: Any) -> None:
        ws = self.workspaces.get(serial)
        if not ws:
            return
        t0 = time.perf_counter()
        img = data if isinstance(data, QImage) else QImage.fromData(data)
        self.perf.record("frame_decode", (time.perf_counter() - t0) * 1000.0)
        if img.isNull():
            return
        is_active = serial == self.active_workspace_serial
        if not is_active:
            ws.last_frame_image = img.copy()
            ws.last_frame_size = (img.width(), img.height())
        if ws.recorder:
            tw = time.perf_counter()
            ws.recorder.record_frame(img, reason="periodic")
            self.perf.record("recorder_write", (time.perf_counter() - tw) * 1000.0)
        if is_active:
            self.on_frame(img)
            ws.stream_scale = self.stream_scale
            ws.dump_bounds = self.dump_bounds
            ws.device_bounds = self.device_bounds

    def on_workspace_tree(self, serial: str, xml_str: str, changed: bool) -> None:
        ws = self.workspaces.get(serial)
        if not ws:
            return
        ws.last_xml = xml_str
        if ws.recorder and changed:
            tw = time.perf_counter()
            ws.recorder.record_xml_dump(xml_str, reason="changed")
            self.perf.record("recorder_write", (time.perf_counter() - tw) * 1000.0)
        if serial == self.active_workspace_serial:
            self.on_tree_data(xml_str, changed)
            ws.dump_bounds = self.dump_bounds

    def on_workspace_log_line(self, serial: str, line: str, source: str = "logcat") -> None:
        ws = self.workspaces.get(serial)
        if not ws:
            return
        ws.log_lines.append(line)
        if len(ws.log_lines) > 8000:
            ws.log_lines = ws.log_lines[-8000:]
        if ws.recorder:
            ws.recorder.record_log_line(line, source=source)
        if serial == self.active_workspace_serial:
            self.txt_log.append(line)

    def on_workspace_focus(self, serial: str, focus: str) -> None:
        ws = self.workspaces.get(serial)
        if not ws:
            return
        ws.focus_text = focus
        if ws.recorder:
            ws.recorder.record_event("focus_changed", {"focus": focus})
        if serial == self.active_workspace_serial:
            self.on_focus_changed(focus)

    def on_workspace_dump_error(self, serial: str, msg: str) -> None:
        ws = self.workspaces.get(serial)
        if ws and ws.recorder:
            ws.recorder.record_event("dump_error", {"message": msg})
        if serial == self.active_workspace_serial:
            self.on_dump_error(msg)

    def on_frame(self, data):
        tr = time.perf_counter()
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
        prev_size = self.last_frame_size
        self.last_frame_size = (img.width(), img.height())
        if not self.pixmap_item:
            self.pixmap_item = self.scene.addPixmap(QPixmap.fromImage(img))
            self.pixmap_item.setZValue(0)
            self.handle_resize()
        else:
            self.pixmap_item.setPixmap(QPixmap.fromImage(img))
        if prev_size != self.last_frame_size:
            self.log_sys(f"Live frame: {img.width()}x{img.height()} (dump bounds: {self.dump_bounds})")
        self.fps_counter += 1
        ws = self._active_workspace()
        if ws:
            ws.last_frame_image = self.last_frame_image.copy() if self.last_frame_image else None
            ws.last_frame_size = self.last_frame_size
            ws.stream_scale = self.stream_scale
            ws.dump_bounds = self.dump_bounds
        self.perf.record("frame_render", (time.perf_counter() - tr) * 1000.0)

    def update_fps(self):
        self.lbl_fps.setText(f"FPS: {self.fps_counter}")
        self.lbl_perf.setText(f"Perf: {self.perf.summary()}")
        self.fps_counter = 0
        if self.perf.should_emit():
            self.log_sys(f"Perf {self.perf.summary()}")

    def log_device_info(self):
        if not self.active_device:
            return
        ws = self._active_workspace()
        meta = AdbManager.get_device_meta(self.active_device)
        self.log_sys(f"Device model: {meta.get('model', 'Unknown')} | serial: {meta.get('serialno', 'n/a')}")
        size = AdbManager.get_screen_size(self.active_device)
        if size:
            self.device_bounds = (0, 0, size[0], size[1])
            if ws:
                ws.device_bounds = self.device_bounds
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
        if ws:
            self.log_sys(f"Workspace profile: {ws.profile} | environment: {ws.environment_type}")

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

        ws = self._active_workspace()
        target_display = ws.selected_display_id if ws else None
        if target_display is not None:
            for i in range(self.combo_display.count()):
                if self.combo_display.itemData(i) == target_display:
                    self.combo_display.setCurrentIndex(i)
                    break

        self.combo_display.blockSignals(False)

    def on_display_change(self, idx: int) -> None:
        if not self.active_device:
            return
        display_id = self.combo_display.itemData(idx)
        self.selected_display_id = display_id
        ws = self._active_workspace()
        if ws:
            ws.selected_display_id = display_id
            if ws.recorder:
                ws.recorder.record_event("display_changed", {"display_id": display_id})
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

        ws = self._active_workspace()
        if ws:
            ws.last_xml = xml_str

        tp = time.perf_counter()
        root, parse_err = UixParser.parse(xml_str)
        self.perf.record("xml_parse", (time.perf_counter() - tp) * 1000.0)
        self.root_node = root
        if root and root.valid_bounds:
            self.dump_bounds = root.rect
        else:
            self.dump_bounds = None
        
        self.tree.clear(); self.current_node_map = {}; self.node_to_item_map = {}; self.rect_map = []
        if root:
            self.populate_tree(root, self.tree)
            self.rect_map_sorted = sort_rects_by_area(self.rect_map)
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
            self.rect_map_sorted = []

        if root and not self.rect_map:
            self.log_sys("Snapshot flagged: zero valid element bounds detected.")
        if ws:
            ws.dump_bounds = self.dump_bounds
        
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
        self.rect_map_sorted = []
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

    def scene_to_dump_coords(self, x: int, y: int) -> tuple[int, int]:
        sx, sy, ox, oy = self.get_bounds_transform()
        if sx <= 0 or sy <= 0:
            return (x, y)
        return (int(x / sx + ox), int(y / sy + oy))

    def find_best_node_at_scene(self, x: int, y: int):
        if not self.rect_map:
            return None
        dx, dy = self.scene_to_dump_coords(x, y)
        rect_source = self.rect_map_sorted if self.rect_map_sorted else self.rect_map
        return smallest_hit(rect_source, dx, dy)

    def on_mouse_hover(self, x, y):
        self.lbl_coords.setText(f"X: {x}, Y: {y}")
        now = time.monotonic()
        if (now - self.last_hover_ts) < 0.012:
            return
        self.last_hover_ts = now
        best_node = self.find_best_node_at_scene(x, y)
        if best_node:
            self.view.setCursor(Qt.PointingHandCursor if best_node.clickable else Qt.ArrowCursor)
            if self.auto_follow_hover and not self.locked_node:
                self.select_node(best_node, scroll=True)
        else:
            self.view.setCursor(Qt.ArrowCursor)

    def handle_tap(self, x, y):
        # Always log the tap coordinate to help users who need manual test coordinates (System UI workaround)
        if self.video_thread:
            dx, dy = self.to_device_coords(x, y)
            # Log as raw coords AND as a copy-pasteable Java snippet
            self.log_sys(f"👆 Tap({int(dx)}, {int(dy)})")
            self.log_sys(f"   📋 Java: clickSystemCoordinate({int(dx)}, {int(dy)});")
            
            AdbManager.tap(self.active_device, dx, dy)
            ws = self._active_workspace()
            if ws and ws.recorder:
                ws.recorder.record_event("tap", {"x": int(dx), "y": int(dy)})
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
            ws = self._active_workspace()
            if ws and ws.recorder:
                ws.recorder.record_event(
                    "swipe",
                    {"x1": int(dx1), "y1": int(dy1), "x2": int(dx2), "y2": int(dy2)},
                )
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
        if not self.active_device:
            return
        d = QFileDialog.getExistingDirectory(self, "Save Snapshot")
        if d:
            ws = self._active_workspace()
            if ws and ws.recorder and ws.video_thread:
                path = ws.recorder.export_snapshot(destination_root=Path(d), bookmark_label="manual")
                ws.last_snapshot_path = str(path)
                self.last_snapshot_path = str(path)
                self.btn_recapture.setEnabled(True)
                self.log_sys(f"Snapshot bookmark exported from live session: {path}")
                return

            path = os.path.join(d, f"snap_{int(time.time())}")
            AdbManager.capture_snapshot(self.active_device, path)
            if self.last_frame_image and not self.last_frame_image.isNull():
                self.last_frame_image.save(os.path.join(path, "screenshot.png"), "PNG")
                self.log_sys("Snapshot image saved from live frame cache")
            else:
                self.log_sys("Snapshot image saved from ADB screencap")
            self.load_snapshot(path)
            self.last_snapshot_path = path
            if ws:
                ws.last_snapshot_path = path
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
        ws = self._active_workspace()
        if ws:
            ws.last_snapshot_path = path
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

    def toggle_emulator_beta(self) -> None:
        self.settings.emulator_beta_enabled = self.chk_emulator_beta.isChecked()
        self.settings.save()
        state = "enabled" if self.settings.emulator_beta_enabled else "disabled"
        self.log_sys(f"Emulator beta support {state}")

    def save_maestro_workspace(self) -> None:
        self.settings.maestro_workspace_path = self.input_maestro_workspace.text().strip()
        self.settings.save()
        if self.settings.maestro_workspace_path:
            self.log_sys(f"Maestro workspace set: {self.settings.maestro_workspace_path}")

    def browse_maestro_workspace(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Maestro Workspace")
        if not d:
            return
        self.input_maestro_workspace.setText(d)
        self.save_maestro_workspace()

    def export_active_session_to_maestro(self) -> None:
        ws = self._active_workspace()
        if not ws or not ws.recorder:
            self.log_sys("No active live session recorder found for Maestro handoff export.")
            return
        workspace_path = self.input_maestro_workspace.text().strip()
        if not workspace_path:
            self.log_sys("Set a Maestro workspace path before exporting handoff.")
            return
        self.save_maestro_workspace()
        result = export_session_handoff(
            session_dir=ws.recorder.session_dir,
            maestro_workspace=Path(workspace_path),
            locator_suggestions=getattr(self, "current_suggestions", []),
        )
        ws.last_handoff_manifest = str(result["manifest_path"])
        self.last_handoff_manifest = ws.last_handoff_manifest
        self.log_sys(f"Maestro handoff exported: {result['export_dir']}")
        self.log_sys(f"Handoff manifest: {result['manifest_path']}")

    def open_last_handoff_folder(self) -> None:
        manifest = self.last_handoff_manifest
        if not manifest:
            self.log_sys("No handoff manifest available to open.")
            return
        folder = Path(manifest).parent
        if not folder.exists():
            self.log_sys(f"Handoff folder not found: {folder}")
            return
        try:
            os.startfile(str(folder))  # type: ignore[attr-defined]
            self.log_sys(f"Opened handoff folder: {folder}")
        except Exception as ex:
            self.log_sys(f"Failed to open folder: {ex}")

    def copy_last_handoff_manifest(self) -> None:
        if not self.last_handoff_manifest:
            self.log_sys("No handoff manifest available to copy.")
            return
        QApplication.clipboard().setText(self.last_handoff_manifest)
        self.log_sys("Handoff manifest path copied to clipboard.")

    def open_maestro_flows(self) -> None:
        workspace_path = self.input_maestro_workspace.text().strip()
        if not workspace_path:
            self.log_sys("Set a Maestro workspace path before opening flows.")
            return
        flows = Path(workspace_path) / "flows"
        if not flows.exists():
            self.log_sys(f"Maestro flows folder not found: {flows}")
            return
        try:
            os.startfile(str(flows))  # type: ignore[attr-defined]
            self.log_sys(f"Opened Maestro flows folder: {flows}")
        except Exception as ex:
            self.log_sys(f"Failed to open Maestro flows folder: {ex}")

    def refresh_timeline_sessions(self) -> None:
        if not hasattr(self, "combo_timeline_session"):
            return
        root = self.settings.session_root_path()
        sessions = []
        for path in root.iterdir():
            if path.is_dir() and (path / "session.db").exists():
                sessions.append(path)
        sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        self.combo_timeline_session.blockSignals(True)
        self.combo_timeline_session.clear()
        for session_dir in sessions:
            label = session_dir.name
            meta_path = session_dir / "meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    label = f"{meta.get('model', 'Unknown')} [{meta.get('serial', 'n/a')}] - {session_dir.name}"
                except Exception:
                    pass
            self.combo_timeline_session.addItem(label, str(session_dir))
        self.combo_timeline_session.blockSignals(False)
        if sessions:
            self.load_selected_timeline_session()
        else:
            if hasattr(self, "tbl_timeline"):
                self.tbl_timeline.setRowCount(0)
                self.txt_timeline_detail.setText("No sessions found.")

    def _selected_timeline_dir(self) -> Optional[Path]:
        if not hasattr(self, "combo_timeline_session"):
            return None
        raw = self.combo_timeline_session.currentData()
        if not raw:
            return None
        path = Path(str(raw))
        if not path.exists():
            return None
        return path

    def load_selected_timeline_session(self) -> None:
        session_dir = self._selected_timeline_dir()
        if not session_dir or not hasattr(self, "tbl_timeline"):
            return
        db_path = session_dir / "session.db"
        if not db_path.exists():
            self.log_sys(f"Session DB not found: {db_path}")
            return

        rows = []
        try:
            con = sqlite3.connect(str(db_path))
            cursor = con.execute(
                "SELECT ts, kind, file_relpath, payload_json FROM events ORDER BY id DESC LIMIT 1500"
            )
            rows = cursor.fetchall()
            con.close()
        except Exception as ex:
            self.log_sys(f"Failed loading timeline events: {ex}")
            return

        self.timeline_event_file_paths = {}
        self.timeline_event_payloads = {}
        self.tbl_timeline.setRowCount(0)
        for idx, (ts, kind, file_relpath, payload_json) in enumerate(rows):
            self.tbl_timeline.insertRow(idx)
            ts_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))
            self.tbl_timeline.setItem(idx, 0, QTableWidgetItem(ts_text))
            self.tbl_timeline.setItem(idx, 1, QTableWidgetItem(str(kind)))
            self.tbl_timeline.setItem(idx, 2, QTableWidgetItem(str(file_relpath or "")))
            preview = str(payload_json or "")[:180]
            self.tbl_timeline.setItem(idx, 3, QTableWidgetItem(preview))
            self.timeline_event_payloads[idx] = str(payload_json or "")
            if file_relpath:
                self.timeline_event_file_paths[idx] = str((session_dir / str(file_relpath)).resolve())
        self.txt_timeline_detail.setText(f"Loaded {len(rows)} events from {session_dir}")

    def on_timeline_selection_changed(self) -> None:
        if not hasattr(self, "tbl_timeline"):
            return
        items = self.tbl_timeline.selectedItems()
        if not items:
            return
        row = items[0].row()
        payload_text = self.timeline_event_payloads.get(row, "")
        file_item = self.tbl_timeline.item(row, 2)
        detail = []
        if file_item and file_item.text():
            detail.append(f"File: {file_item.text()}")
        if payload_text:
            detail.append(payload_text)
        self.txt_timeline_detail.setText("\n".join(detail))

    def open_selected_timeline_session(self) -> None:
        session_dir = self._selected_timeline_dir()
        if not session_dir:
            self.log_sys("No timeline session selected.")
            return
        try:
            os.startfile(str(session_dir))  # type: ignore[attr-defined]
        except Exception as ex:
            self.log_sys(f"Failed to open session folder: {ex}")

    def open_selected_timeline_file(self) -> None:
        if not hasattr(self, "tbl_timeline"):
            return
        items = self.tbl_timeline.selectedItems()
        if not items:
            self.log_sys("Select a timeline row first.")
            return
        row = items[0].row()
        file_path = self.timeline_event_file_paths.get(row)
        if not file_path:
            self.log_sys("Selected event has no file attached.")
            return
        path = Path(file_path)
        if not path.exists():
            self.log_sys(f"Event file does not exist: {file_path}")
            return
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as ex:
            self.log_sys(f"Failed to open event file: {ex}")

    def export_selected_timeline_to_maestro(self) -> None:
        session_dir = self._selected_timeline_dir()
        if not session_dir:
            self.log_sys("No timeline session selected for export.")
            return
        workspace_path = self.input_maestro_workspace.text().strip()
        if not workspace_path:
            self.log_sys("Set a Maestro workspace path before exporting.")
            return
        self.save_maestro_workspace()
        result = export_session_handoff(
            session_dir=session_dir,
            maestro_workspace=Path(workspace_path),
            locator_suggestions=getattr(self, "current_suggestions", []),
        )
        self.last_handoff_manifest = str(result["manifest_path"])
        self.log_sys(f"Timeline session exported: {result['export_dir']}")

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
            if not self.ambient_player:
                self.init_ambient_video()
                if not self.ambient_enabled:
                    self.chk_ambient.blockSignals(True)
                    self.chk_ambient.setChecked(False)
                    self.chk_ambient.blockSignals(False)
                    return
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
        for ws in list(self.workspaces.values()):
            if ws.video_thread:
                self.stop_live_for_workspace(ws)
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
        return self.find_best_node_at_scene(x, y)

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
        ws = self._active_workspace()
        if ws:
            ws.focus_text = focus
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
        ws = self._active_workspace()
        if ws:
            ws.last_snapshot_path = self.last_snapshot_path
        self.log_sys(f"Snapshot re-captured: {self.last_snapshot_path}")

    def toggle_perf_mode(self) -> None:
        self.perf_mode = self.chk_perf.isChecked()
        if self.perf_mode:
            self.ambient_frame_interval_ms = 140
        else:
            self.ambient_frame_interval_ms = 90
        self._apply_background_scheduler()
        if self.video_thread and hasattr(self.video_thread, "target_fps"):
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
