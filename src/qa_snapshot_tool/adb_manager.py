"""
ADB Manager Module.

This module provides a robust interface for interacting with Android devices via the
Android Debug Bridge (ADB). It handles device discovery, screen capture, UI automation
dumps, and logcat retrieval with error handling and platform-specific adjustments.
"""

import subprocess
import os
import json
import time
from typing import List, Dict, Optional, Any

class AdbManager:
    """
    Static utility class for ADB operations.
    """
    _display_ids_cache: Dict[str, List[str]] = {}
    _best_display_id: Dict[str, str] = {}

    @staticmethod
    def getprop(serial: str, prop: str) -> str:
        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'getprop', prop], timeout=5)
        return (res.stdout or "").strip()

    @staticmethod
    def _run_cmd(cmd: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
        """
        Executes a shell command with a timeout and captures the output.

        Args:
            cmd (List[str]): The command to execute as a list of strings.
            timeout (int, optional): Maximum time in seconds to wait for command completion. Defaults to 10.

        Returns:
            subprocess.CompletedProcess: The result of the executed command. 
            Returns a dummy ComplatedProcess with returncode -1 on exception.
        """
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO() # type: ignore
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW # type: ignore
        
        try:
            res = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace', 
                startupinfo=startupinfo, 
                check=False, 
                timeout=timeout
            )
            return res
        except Exception as e:
            return subprocess.CompletedProcess(cmd, -1, "", str(e))

    @staticmethod
    def _run_bytes_cmd(cmd: List[str]) -> Optional[subprocess.CompletedProcess]:
        """
        Executes a shell command and captures binary output.

        Args:
            cmd (List[str]): The command to execute.

        Returns:
            Optional[subprocess.CompletedProcess]: The process result, or None if an error occurs.
        """
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO() # type: ignore
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW # type: ignore
        try:
            return subprocess.run(
                cmd, 
                capture_output=True, 
                startupinfo=startupinfo, 
                check=False, 
                timeout=5
            )
        except Exception: 
            return None

    @staticmethod
    def get_devices_detailed() -> List[Dict[str, str]]:
        """
        Retrieves a list of connected devices with details.

        Returns:
            List[Dict[str, str]]: A list of dictionaries, each containing 'serial' and 'model' keys.
        """
        try:
            res = AdbManager._run_cmd(['adb', 'devices', '-l'])
            lines = res.stdout.strip().split('\n')[1:] 
            devices: List[Dict[str, str]] = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    details = {"serial": parts[0], "model": "Unknown"}
                    for p in parts[2:]:
                        if "model:" in p: 
                            details["model"] = p.split(":")[1]
                    devices.append(details)
            return devices
        except Exception: 
            return []

    @staticmethod
    def connect_ip(address: str) -> str:
        res = AdbManager._run_cmd(['adb', 'connect', address], timeout=10)
        return (res.stdout or res.stderr).strip()

    @staticmethod
    def disconnect_ip(address: str) -> str:
        res = AdbManager._run_cmd(['adb', 'disconnect', address], timeout=10)
        return (res.stdout or res.stderr).strip()

    @staticmethod
    def _history_path() -> str:
        base = os.path.join(os.path.expanduser("~"), ".qa_snapshot_tool")
        if not os.path.exists(base):
            os.makedirs(base, exist_ok=True)
        return os.path.join(base, "device_history.json")

    @staticmethod
    def load_device_history() -> List[Dict[str, str]]:
        path = AdbManager._history_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    @staticmethod
    def save_device_history(entries: List[Dict[str, str]]) -> None:
        path = AdbManager._history_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)

    @staticmethod
    def record_device(serial: str, model: str) -> None:
        entries = AdbManager.load_device_history()
        now = str(int(time.time()))
        updated = [e for e in entries if e.get("serial") != serial]
        updated.insert(0, {"serial": serial, "model": model, "last_seen": now})
        AdbManager.save_device_history(updated[:20])

    @staticmethod
    def get_screenshot_bytes(serial: str) -> Optional[bytes]:
        """
        Captures a screenshot from the specified device as raw PNG bytes.

        Args:
            serial (str): The device serial number.

        Returns:
            Optional[bytes]: The PNG image data, or None if capture failed.
        """
        # -p is essential for PNG format
        best_bytes: Optional[bytes] = None
        best_len = 0
        best_id = None

        # If we already know the best display id, try it first
        preferred_id = AdbManager._best_display_id.get(serial)
        if preferred_id:
            res = AdbManager._run_bytes_cmd(['adb', '-s', serial, 'exec-out', 'screencap', '-p', '-d', preferred_id])
            if res and res.returncode == 0 and res.stdout:
                return res.stdout

        display_ids = AdbManager.get_display_ids(serial)
        fallback_ids = ["0", "1", "2", "3", "4", "5"]
        candidates = list(dict.fromkeys(display_ids + fallback_ids))

        for disp_id in candidates:
            res = AdbManager._run_bytes_cmd(['adb', '-s', serial, 'exec-out', 'screencap', '-p', '-d', disp_id])
            if res and res.returncode == 0 and res.stdout:
                size = len(res.stdout)
                if size > best_len:
                    best_len = size
                    best_bytes = res.stdout
                    best_id = disp_id

        if best_id:
            AdbManager._best_display_id[serial] = best_id
        return best_bytes

    @staticmethod
    def get_display_ids(serial: str) -> List[str]:
        """
        Retrieves SurfaceFlinger display IDs for multi-display devices.
        """
        if serial in AdbManager._display_ids_cache:
            return AdbManager._display_ids_cache[serial]
        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'SurfaceFlinger', '--display-id'], timeout=10)
        ids: List[str] = []
        if res and res.stdout:
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("Display ") or line.startswith("Virtual Display "):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        ids.append(parts[1])
        AdbManager._display_ids_cache[serial] = ids
        return ids

    @staticmethod
    def get_power_summary(serial: str) -> Dict[str, str]:
        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'power'], timeout=8)
        wakefulness = "Unknown"
        interactive = "Unknown"
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("mWakefulness="):
                wakefulness = line.split("=", 1)[1]
            if line.startswith("mInteractive="):
                interactive = line.split("=", 1)[1]
        return {"wakefulness": wakefulness, "interactive": interactive}

    @staticmethod
    def get_display_summary(serial: str) -> List[str]:
        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'display'], timeout=10)
        summaries: List[str] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("DisplayDeviceInfo{"):
                summaries.append(line)
        return summaries

    @staticmethod
    def get_device_meta(serial: str) -> Dict[str, Any]:
        now = int(time.time())
        model = AdbManager.getprop(serial, "ro.product.model")
        serialno = AdbManager.getprop(serial, "ro.serialno")
        display_ids = AdbManager.get_display_ids(serial)
        power = AdbManager.get_power_summary(serial)
        return {
            "timestamp": now,
            "serial": serial,
            "serialno": serialno,
            "model": model,
            "display_ids": display_ids,
            "power": power,
        }

    @staticmethod
    def get_xml_dump(serial: str) -> Optional[str]:
        """ 
        Retrieves the UI hierarchy dump from the device.
        Uses a robust file-based strategy to handle complex UI trees that might choke the direct pipe.

        Args:
            serial (str): The device serial number.

        Returns:
            Optional[str]: The XML string of the UI hierarchy, or None on failure.
        """
        # Strategy 2: File based (Slow but Reliable) - The "Holy Water" method
        temp_path = "/sdcard/window_dump.xml"
        
        # Delete old first to ensure we don't read stale data
        AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'rm', temp_path])
        
        # Dump
        AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'uiautomator', 'dump', temp_path], timeout=15)
        
        # Check size (if it's small, it failed or captured only root)
        check = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'du', '-b', temp_path])
        try:
            # Output format: "12345   /sdcard/window_dump.xml"
            size = int(check.stdout.split()[0])
            if size < 200: 
                return None # Trash dump
        except (IndexError, ValueError): 
            pass

        # Pull content via cat (faster than adb pull to local file)
        res_cat = AdbManager._run_cmd(['adb', '-s', serial, 'exec-out', 'cat', temp_path])
        return res_cat.stdout

    @staticmethod
    def get_current_focus(serial: str) -> str:
        """
        Retrieves the name of the currently focused window/activity.
        """
        try:
            # dumpsys window displays
            cmd = ['adb', '-s', serial, 'shell', 'dumpsys', 'window', 'windows']
            res = AdbManager._run_cmd(cmd)
            for line in res.stdout.split('\n'):
                if 'mCurrentFocus' in line or 'mFocusedApp' in line:
                    return line.strip()
            return "Unknown"
        except Exception:
            return "Error"

    @staticmethod
    def tap(serial: str, x: int, y: int) -> None:
        """
        Simulates a tap event at the specified coordinates.

        Args:
            serial (str): The device serial number.
            x (int): The x-coordinate.
            y (int): The y-coordinate.
        """
        subprocess.Popen(
            ['adb', '-s', serial, 'shell', 'input', 'tap', str(x), str(y)], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )

    @staticmethod
    def swipe(serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 250) -> None:
        """
        Simulates a swipe event from (x1, y1) to (x2, y2).

        Args:
            serial (str): The device serial number.
            x1 (int): Start x.
            y1 (int): Start y.
            x2 (int): End x.
            y2 (int): End y.
            duration_ms (int): Duration in milliseconds.
        """
        subprocess.Popen(
            ['adb', '-s', serial, 'shell', 'input', 'swipe', str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    @staticmethod
    def capture_snapshot(serial: str, folder: str) -> None:
        """
        Captures a complete snapshot (screenshot, XML dump, logcat) to the specified folder.

        Args:
            serial (str): The device serial number.
            folder (str): The destination directory path.
        """
        if not os.path.exists(folder): 
            os.makedirs(folder)
        
        png_bytes = AdbManager.get_screenshot_bytes(serial)
        if png_bytes:
            with open(os.path.join(folder, 'screenshot.png'), 'wb') as f: 
                f.write(png_bytes)

        xml_str = AdbManager.get_xml_dump(serial)
        with open(os.path.join(folder, 'dump.uix'), 'w', encoding='utf-8') as f:
            if xml_str: 
                f.write(xml_str)
            else: 
                f.write("<error>Failed to capture dump</error>")

        res = AdbManager._run_cmd(['adb', '-s', serial, 'logcat', '-d', '-t', '500'])
        with open(os.path.join(folder, 'logcat.txt'), 'w', encoding='utf-8') as f: 
            f.write(res.stdout)

        focus = AdbManager.get_current_focus(serial)
        with open(os.path.join(folder, 'focus.txt'), 'w', encoding='utf-8') as f:
            f.write(focus)

        meta = AdbManager.get_device_meta(serial)
        meta["focus"] = focus
        with open(os.path.join(folder, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
