import subprocess
import os
import time
import json
from typing import List, Tuple

class AdbCapture:
    @staticmethod
    def get_devices() -> List[str]:
        try:
            result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')[1:] # Skip header
            devices = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    serial = parts[0]
                    state = parts[1] if len(parts) > 1 else "unknown"
                    model = "Unknown"
                    for part in parts:
                        if part.startswith("model:"):
                            model = part.split(":")[1]
                    devices.append(f"{serial} ({model}) - {state}")
            return devices
        except FileNotFoundError:
            return ["Error: ADB not found in PATH"]

    @staticmethod
    def capture_snapshot(device_serial: str, output_folder: str) -> Tuple[bool, str]:
        """
        Captures screenshot, uix dump, logcat tail, and window focus info.
        """
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # Clean serial (remove extra info if selected from UI list)
        serial = device_serial.split()[0]
        adb_cmd = ["adb", "-s", serial]

        print(f"Capturing snapshot for {serial} to {output_folder}...")

        # 1. Screenshot
        subprocess.run(adb_cmd + ["shell", "screencap", "-p", "/sdcard/temp_screenshot.png"], check=False)
        subprocess.run(adb_cmd + ["pull", "/sdcard/temp_screenshot.png", os.path.join(output_folder, "screenshot.png")], check=False)
        subprocess.run(adb_cmd + ["shell", "rm", "/sdcard/temp_screenshot.png"], check=False)

        # 2. UI Dump
        # Old method: uiautomator dump. Newer Android might require different handling, but this is standard.
        subprocess.run(adb_cmd + ["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], check=False)
        subprocess.run(adb_cmd + ["pull", "/sdcard/window_dump.xml", os.path.join(output_folder, "dump.uix")], check=False)
        
        # 3. Logcat (Tail 200)
        try:
            with open(os.path.join(output_folder, "logcat.txt"), "w", encoding="utf-8") as f:
                subprocess.run(adb_cmd + ["logcat", "-d", "-t", "200"], stdout=f, check=False)
        except Exception:
            pass

        # 4. Meta Data (Focus, Timestamp)
        meta = {
            "timestamp": time.time(),
            "device": serial,
            "focus": ""
        }
        
        # Try to get current focus
        try:
            focus_res = subprocess.run(adb_cmd + ["shell", "dumpsys", "window", "windows"], capture_output=True, text=True, check=False)
            for line in focus_res.stdout.split("\n"):
                if "mCurrentFocus" in line:
                    meta["focus"] = line.strip()
                    break
        except Exception:
            pass

        with open(os.path.join(output_folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return True, output_folder