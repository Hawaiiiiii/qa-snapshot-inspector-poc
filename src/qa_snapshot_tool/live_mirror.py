from PySide6.QtCore import QThread, Signal
from adb_manager import AdbManager
import hashlib
import time
import subprocess

class VideoThread(QThread):
    """ High FPS Screenshot Loop """
    frame_ready = Signal(bytes) # Raw PNG data
    
    def __init__(self, serial):
        super().__init__()
        self.serial = serial
        self.running = True

    def run(self):
        while self.running:
            # Fetch bytes directly
            data = AdbManager.get_screenshot_bytes(self.serial)
            if data:
                self.frame_ready.emit(data)
            else:
                time.sleep(0.5) # Error backoff
            
            # Tiny sleep to prevent CPU hogging, but allow near max FPS
            time.sleep(0.01)

    def stop(self):
        self.running = False
        self.wait()

class HierarchyThread(QThread):
    """ Slower XML Loop (Async) """
    tree_ready = Signal(str, bool) # XML String, is_changed
    
    def __init__(self, serial):
        super().__init__()
        self.serial = serial
        self.running = True
        self.last_hash = ""

    def run(self):
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
                if not self.running: break
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.wait()

class LogcatThread(QThread):
    """ Real-time Log Stream """
    log_line = Signal(str)
    
    def __init__(self, serial):
        super().__init__()
        self.serial = serial
        self.running = True
        self.proc = None

    def run(self):
        # Clear buffer first
        subprocess.run(['adb', '-s', self.serial, 'logcat', '-c'], check=False)
        
        # Start streaming
        cmd = ['adb', '-s', self.serial, 'logcat', '-v', 'time']
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                     text=True, encoding='utf-8', errors='replace')
        
        while self.running:
            line = self.proc.stdout.readline()
            if not line:
                break
            if line.strip():
                self.log_line.emit(line.strip())
        
        if self.proc: self.proc.terminate()

    def stop(self):
        self.running = False
        if self.proc: self.proc.terminate()
        self.wait()

class FocusMonitorThread(QThread):
    """ Checks Window Focus periodically """
    focus_changed = Signal(str)

    def __init__(self, serial):
        super().__init__()
        self.serial = serial
        self.running = True
    
    def run(self):
        last_focus = ""
        while self.running:
            f = AdbManager.get_current_focus(self.serial)
            if f != last_focus:
                last_focus = f
                self.focus_changed.emit(f)
            time.sleep(1.0) # Check every second
            
    def stop(self):
        self.running = False
        self.wait()