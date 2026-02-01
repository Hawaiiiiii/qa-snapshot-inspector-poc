"""
Live Mirroring Module.

Provides background threads for real-time device interaction:
- Video stream (Screenshot polling)
- Hierarchy polling (Async XML fetching)
- Logcat streaming
- Focus monitoring
"""

from PySide6.QtCore import QThread, Signal
import hashlib
import time
import subprocess
from typing import Optional
from qa_snapshot_tool.adb_manager import AdbManager

class VideoThread(QThread):
    """ 
    High FPS Screenshot Loop. 
    Continuously fetches screenshots to simulate a video feed.
    """
    frame_ready = Signal(bytes) # Emits Raw PNG data
    
    def __init__(self, serial: str):
        super().__init__()
        self.serial = serial
        self.running = True

    def run(self) -> None:
        while self.running:
            # Fetch bytes directly
            data = AdbManager.get_screenshot_bytes(self.serial)
            if data:
                self.frame_ready.emit(data)
            else:
                time.sleep(0.5) # Error backoff
            
            # Tiny sleep to prevent CPU hogging, but allow near max FPS
            time.sleep(0.01)

    def stop(self) -> None:
        self.running = False
        self.wait()

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
                time.sleep(0.1)

    def stop(self) -> None:
        self.running = False
        self.wait()

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
