from PySide6.QtCore import QThread, Signal
from adb_manager import AdbManager
import os
import time
import json
import hashlib

class LiveInspectorThread(QThread):
    # Signal: (image_path, xml_path, meta_data, is_new_xml)
    data_ready = Signal(str, str, dict, bool)
    log_msg = Signal(str)

    def __init__(self, serial, session_folder):
        super().__init__()
        self.serial = serial
        self.session_folder = session_folder
        self.running = True
        self.last_xml_hash = ""
        self.sequence = 0

    def run(self):
        self.log_msg.emit(f"Starting Live Inspector Loop for {self.serial}")
        
        while self.running:
            start_time = time.time()
            
            # Define filenames
            seq_str = f"{self.sequence:03d}"
            dump_name = f"dump_{seq_str}.uix"
            img_name = f"screen_{seq_str}.png"
            meta_name = f"meta_{seq_str}.json"
            
            dump_path = os.path.join(self.session_folder, dump_name)
            img_path = os.path.join(self.session_folder, img_name)
            meta_path = os.path.join(self.session_folder, meta_name)

            # Capture
            try:
                AdbManager.capture_snapshot_raw(self.serial, dump_path, img_path)
                
                # Check XML Hash
                is_new_xml = False
                current_hash = self._get_file_hash(dump_path)
                
                if current_hash != self.last_xml_hash:
                    self.last_xml_hash = current_hash
                    is_new_xml = True
                
                # Create Meta
                meta = {
                    "sequence": self.sequence,
                    "timestamp": time.time(),
                    "serial": self.serial,
                    "xml_changed": is_new_xml
                }
                with open(meta_path, 'w') as f:
                    json.dump(meta, f, indent=2)

                # Emit Update
                self.data_ready.emit(img_path, dump_path, meta, is_new_xml)
                
                self.sequence += 1

            except Exception as e:
                self.log_msg.emit(f"Live Loop Error: {str(e)}")
                time.sleep(1) # Backoff on error

            # Throttle to ~1.5s (UI Dump is slow, we don't want to choke ADB)
            elapsed = time.time() - start_time
            sleep_time = max(0.1, 1.5 - elapsed)
            time.sleep(sleep_time)

    def stop(self):
        self.running = False
        self.wait()

    def _get_file_hash(self, path):
        if not os.path.exists(path): return ""
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()