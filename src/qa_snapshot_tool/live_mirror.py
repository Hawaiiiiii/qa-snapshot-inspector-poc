"""
Live Mirroring Module.

Provides background threads for real-time device interaction:
- Video stream (Screenshot polling)
- Hierarchy polling (Async XML fetching)
- Logcat streaming
- Focus monitoring
"""

from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtGui import QImage
from PySide6.QtGui import QGuiApplication
import hashlib
import time
import subprocess
import threading
import shutil
import ctypes
from ctypes import wintypes
from typing import Optional, Protocol, runtime_checkable
from qa_snapshot_tool.adb_manager import AdbManager

@runtime_checkable
class VideoSourceInterface(Protocol):
    frame_ready: Signal

    def start_stream(self) -> None: ...
    def stop_stream(self) -> None: ...
    def set_target_fps(self, fps: int) -> None: ...

class VideoThread(QThread):
    """ 
    High FPS Screenshot Loop. 
    Continuously fetches screenshots to simulate a video feed.
    """
    frame_ready = Signal(object) # Emits Raw PNG bytes
    
    def __init__(self, serial: str, target_fps: int = 6):
        super().__init__()
        self.serial = serial
        self.running = True
        self.target_fps = max(1, int(target_fps))

    def run(self) -> None:
        while self.running:
            start = time.time()
            # Fetch bytes directly
            data = AdbManager.get_screenshot_bytes(self.serial)
            if data:
                self.frame_ready.emit(data)
            else:
                time.sleep(0.5) # Error backoff

            # Throttle capture rate for stability
            elapsed = time.time() - start
            frame_budget = 1.0 / max(1, self.target_fps)
            if elapsed < frame_budget:
                time.sleep(frame_budget - elapsed)

    def stop(self) -> None:
        self.running = False
        self.wait()

    def start_stream(self) -> None:
        self.start()

    def stop_stream(self) -> None:
        self.stop()

    def set_target_fps(self, fps: int) -> None:
        self.target_fps = max(1, int(fps))

class ScrcpyVideoSource(QObject):
    """
    High-performance video stream using the scrcpy binary.
    Streams raw H.264 from stdout and decodes with PyAV, fallback to ADB polling.
    """
    frame_ready = Signal(object)  # Emits QImage or bytes when falling back
    log_line = Signal(str)

    def __init__(
        self,
        serial: str,
        max_size: Optional[int] = None,
        max_fps: int = 30,
        bitrate: int = 2_000_000,
        scrcpy_path: Optional[str] = None,
        hide_window: bool = False,
        prefer_raw: bool = True,
    ) -> None:
        super().__init__()
        self.serial = serial
        self.max_size = max_size
        self.max_fps = max_fps
        self.bitrate = bitrate
        self.scrcpy_path = scrcpy_path
        self.hide_window = hide_window
        self.prefer_raw = prefer_raw
        self.target_fps = max_fps
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None
        self._running = False
        self._fallback_source: Optional[VideoThread] = None
        self._supports_raw: Optional[bool] = None
        self._window_title = f"QUANTUM Scrcpy {serial}"
        self._moved_offscreen = False
        self._scrcpy_bin: Optional[str] = None

    def start_stream(self) -> None:
        if self._running:
            return
        self._running = True
        self._start_scrcpy_stream()

    def _start_scrcpy_stream(self) -> None:
        if not self._running:
            return
        scrcpy_bin = self.scrcpy_path or shutil.which("scrcpy")
        if not scrcpy_bin:
            self._start_adb_fallback()
            return
        self._scrcpy_bin = scrcpy_bin
        supports_raw = self._supports_raw
        if supports_raw is None:
            supports_raw = self._detect_raw_support(scrcpy_bin)
            self._supports_raw = supports_raw

        if supports_raw and self.prefer_raw and self._pyav_available():
            self._start_raw_stream(scrcpy_bin)
        else:
            if supports_raw and self.prefer_raw and not self._pyav_available():
                self.log_line.emit("PyAV not installed; falling back to scrcpy window capture")
            self._start_window_capture(scrcpy_bin)

    def _pyav_available(self) -> bool:
        try:
            import av  # type: ignore
            return True
        except Exception:
            return False

    def _detect_raw_support(self, scrcpy_bin: str) -> bool:
        try:
            res = subprocess.run([scrcpy_bin, "--help"], capture_output=True, text=True)
            out = (res.stdout or "") + (res.stderr or "")
            return "--raw-video" in out
        except Exception:
            return False

    def _start_raw_stream(self, scrcpy_bin: str) -> None:
        cmd = [
            scrcpy_bin,
            "--serial",
            self.serial,
            "--no-playback",
            "--no-control",
            "--raw-video=-",
            "--no-audio",
        ]
        if self.max_size:
            cmd += ["--max-size", str(int(self.max_size))]
        if self.max_fps:
            cmd += ["--max-fps", str(int(self.max_fps))]
        if self.bitrate:
            cmd += ["--video-bit-rate", str(int(self.bitrate))]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            self._start_adb_fallback()
            return

        self.log_line.emit("scrcpy raw H.264 decode active (PyAV)")
        self._thread = threading.Thread(target=self._read_raw_stream, daemon=True)
        self._thread.start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _start_window_capture(self, scrcpy_bin: str) -> None:
        cmd = [
            scrcpy_bin,
            "--serial",
            self.serial,
            "--window-title",
            self._window_title,
            "--render-driver",
            "software",
            "--window-borderless",
            "--no-control",
            "--no-audio",
        ]
        if self.hide_window:
            cmd += ["--window-x", "-32000", "--window-y", "-32000"]
        if self.max_size:
            cmd += ["--max-size", str(int(self.max_size))]
        if self.max_fps:
            cmd += ["--max-fps", str(int(self.max_fps))]
        if self.bitrate:
            cmd += ["--video-bit-rate", str(int(self.bitrate))]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            self._start_adb_fallback()
            return

        self.log_line.emit("scrcpy window capture active (PrintWindow)")
        threading.Thread(target=self._read_stderr, daemon=True).start()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        self._thread = threading.Thread(target=self._capture_window_loop, daemon=True)
        self._thread.start()

    def _read_raw_stream(self) -> None:
        if not self._proc or not self._proc.stdout:
            self._start_adb_fallback()
            return
        try:
            import av

            container = av.open(self._proc.stdout, format="h264")
            for frame in container.decode(video=0):
                if not self._running:
                    break
                img = frame.to_ndarray(format="bgr24")
                h, w, ch = img.shape
                bytes_per_line = ch * w
                qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_BGR888)
                try:
                    self.frame_ready.emit(qimg.copy())
                except RuntimeError:
                    self._running = False
                    break
        except ImportError:
            self.log_line.emit("PyAV not installed. Falling back to scrcpy window capture.")
            self._restart_as_window_capture()
        except Exception as ex:
            self.log_line.emit(f"scrcpy decode failed: {ex}")
            self._restart_as_window_capture()

    def _restart_as_window_capture(self) -> None:
        if not self._scrcpy_bin:
            self._start_adb_fallback()
            return
        try:
            if self._proc:
                self._proc.terminate()
        except Exception:
            pass
        self._proc = None
        self._start_window_capture(self._scrcpy_bin)

    def _capture_window_loop(self) -> None:
        hwnd = self._find_window_handle(self._window_title, timeout=5.0)
        if not hwnd:
            self.log_line.emit("scrcpy window not found for capture")
            return
        target_fps = max(1, int(self.max_fps)) if self.max_fps else 30
        frame_budget = 1.0 / target_fps
        while self._running:
            start = time.time()
            img = self._capture_window_image(hwnd)
            if img is not None and not img.isNull():
                if self.hide_window and not self._moved_offscreen:
                    self._move_window_offscreen(hwnd)
                    self._moved_offscreen = True
                try:
                    self.frame_ready.emit(img)
                except RuntimeError:
                    self._running = False
                    break
            elapsed = time.time() - start
            if elapsed < frame_budget:
                time.sleep(frame_budget - elapsed)

    def _find_window_handle(self, title: str, timeout: float = 5.0) -> int:
        try:
            import ctypes

            user32 = ctypes.windll.user32
            end = time.time() + timeout
            while time.time() < end and self._running:
                hwnd = user32.FindWindowW(None, title)
                if hwnd:
                    return int(hwnd)
                time.sleep(0.1)
        except Exception:
            pass
        return 0

    def _move_window_offscreen(self, hwnd: int) -> None:
        try:
            user32 = ctypes.windll.user32
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            user32.SetWindowPos(hwnd, None, -32000, -32000, 0, 0, SWP_NOZORDER | SWP_NOACTIVATE)
        except Exception:
            pass

    def _capture_window_image(self, hwnd: int) -> Optional[QImage]:
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            rect = wintypes.RECT()
            if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
                return None
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width <= 0 or height <= 0:
                return None

            hwnd_dc = user32.GetDC(hwnd)
            mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
            bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
            gdi32.SelectObject(mem_dc, bmp)

            PW_RENDERFULLCONTENT = 0x00000002
            result = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
            if not result:
                gdi32.BitBlt(mem_dc, 0, 0, width, height, hwnd_dc, 0, 0, 0x00CC0020)

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0

            buf_size = width * height * 4
            buffer = (ctypes.c_ubyte * buf_size)()
            gdi32.GetDIBits(mem_dc, bmp, 0, height, buffer, ctypes.byref(bmi), 0)

            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)

            qimg = QImage(bytes(buffer), width, height, QImage.Format_ARGB32)
            return qimg.copy()
        except Exception:
            return None

    def _read_stderr(self) -> None:
        if not self._proc or not self._proc.stderr:
            return
        try:
            for line in self._proc.stderr:
                if not self._running:
                    break
                msg = line.decode("utf-8", errors="replace").strip()
                if msg:
                    self.log_line.emit(msg)
        except Exception:
            pass

    def _read_stdout(self) -> None:
        if not self._proc or not self._proc.stdout:
            return
        try:
            for line in self._proc.stdout:
                if not self._running:
                    break
                if isinstance(line, bytes):
                    msg = line.decode("utf-8", errors="replace").strip()
                else:
                    msg = str(line).strip()
                if msg:
                    self.log_line.emit(msg)
        except Exception:
            pass

    def _start_adb_fallback(self) -> None:
        if self._fallback_source:
            return
        self._fallback_source = VideoThread(self.serial, target_fps=8)
        self._fallback_source.frame_ready.connect(self.frame_ready.emit)
        self._fallback_source.start_stream()

    def stop_stream(self) -> None:
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._fallback_source:
            self._fallback_source.stop_stream()
            self._fallback_source = None

    def set_target_fps(self, fps: int) -> None:
        self.max_fps = max(1, int(fps))
        self.target_fps = self.max_fps
        if self._fallback_source:
            self._fallback_source.set_target_fps(fps)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]

class HierarchyThread(QThread):
    """ 
    Slower XML Loop (Async).
    Polls for UI XML changes at a lower frequency than video.
    """
    tree_ready = Signal(str, bool) # Emits (XML String, is_changed)
    
    def __init__(self, serial: str):
        super().__init__()
        self.serial = serial
        self.running = True
        self.last_hash = ""
        self._refresh_event = threading.Event()

    def run(self) -> None:
        while self.running:
            try:
                xml_str = AdbManager.get_xml_dump(self.serial)
                if xml_str and len(xml_str) > 50:
                    # Only emit if changed to save UI repainting costs
                    cur_hash = hashlib.md5(xml_str.encode()).hexdigest()
                    if cur_hash != self.last_hash:
                        self.last_hash = cur_hash
                        self.tree_ready.emit(xml_str, True)
                    else:
                        # Optional: Emit False if you want to confirm "still same"
                        pass
            except Exception:
                pass
            
            # Poll hierarchy less frequently than video (1.5s is usually good for UI stability)
            for _ in range(15): 
                if not self.running: 
                    break
                if self._refresh_event.wait(timeout=0.1):
                    self._refresh_event.clear()
                    break

    def stop(self) -> None:
        self.running = False
        self.wait()

    def request_refresh(self) -> None:
        self._refresh_event.set()

class LogcatThread(QThread):
    """ 
    Real-time Log Stream.
    Reads 'adb logcat' output line by line.
    """
    log_line = Signal(str)
    
    def __init__(self, serial: str):
        super().__init__()
        self.serial = serial
        self.running = True
        self.proc: Optional[subprocess.Popen] = None

    def run(self) -> None:
        # Clear buffer first
        subprocess.run(['adb', '-s', self.serial, 'logcat', '-c'], check=False)
        
        # Start streaming
        cmd = ['adb', '-s', self.serial, 'logcat', '-v', 'time']
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if self.proc and self.proc.stdout:
            while self.running:
                # Type safe read
                line = self.proc.stdout.readline()
                if not line:
                    break
                if line.strip():
                    self.log_line.emit(line.strip())
        
        if self.proc: 
            self.proc.terminate()

    def stop(self) -> None:
        self.running = False
        if self.proc: 
            self.proc.terminate()
        self.wait()

class FocusMonitorThread(QThread):
    """ 
    Checks Window Focus periodically.
    Useful for detecting activity changes.
    """
    focus_changed = Signal(str)

    def __init__(self, serial: str):
        super().__init__()
        self.serial = serial
        self.running = True
    
    def run(self) -> None:
        last_focus = ""
        while self.running:
            f = AdbManager.get_current_focus(self.serial)
            if f != last_focus:
                last_focus = f
                self.focus_changed.emit(f)
            time.sleep(1.0) # Check every second
            
    def stop(self) -> None:
        self.running = False
        self.wait()
