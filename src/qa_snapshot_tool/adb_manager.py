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
import shutil
import re
from typing import List, Dict, Optional, Any

class AdbManager:
    """
    Static utility class for ADB operations.
    """
    _display_ids_cache: Dict[str, List[str]] = {}
    _best_display_id: Dict[str, str] = {}
    _preferred_display_id: Dict[str, str] = {}
    _last_dump_error: Optional[str] = None
    _display_size_cache: Dict[str, tuple[int, int]] = {}
    _uiautomator_service_cache: Dict[str, bool] = {}

    @staticmethod
    def _normalize_serial(serial: str) -> str:
        return (serial or "").strip()
    _adb_host: Optional[str] = None
    _adb_port: Optional[int] = None

    @staticmethod
    def set_adb_server(host: str, port: int = 5037) -> None:
        AdbManager._adb_host = host
        AdbManager._adb_port = port

    @staticmethod
    def clear_adb_server() -> None:
        AdbManager._adb_host = None
        AdbManager._adb_port = None

    @staticmethod
    def _resolve_adb() -> Optional[str]:
        adb = shutil.which("adb")
        if adb:
            return adb
        candidates: List[str] = []
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if android_home:
            candidates.append(os.path.join(android_home, "platform-tools", "adb"))
            candidates.append(os.path.join(android_home, "platform-tools", "adb.exe"))
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            candidates.append(os.path.join(local_appdata, "Android", "Sdk", "platform-tools", "adb.exe"))
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    @staticmethod
    def _apply_adb_server(cmd: List[str]) -> List[str]:
        if not cmd or cmd[0] != "adb":
            return cmd
        adb_bin = AdbManager._resolve_adb()
        if adb_bin:
            cmd = [adb_bin] + cmd[1:]
        extra: List[str] = []
        if AdbManager._adb_host:
            extra += ["-H", AdbManager._adb_host]
        if AdbManager._adb_port:
            extra += ["-P", str(AdbManager._adb_port)]
        if not extra:
            return cmd
        return [cmd[0]] + extra + cmd[1:]

    @staticmethod
    def getprop(serial: str, prop: str) -> str:
        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'getprop', prop], timeout=5)
        return (res.stdout or "").strip()

    @staticmethod
    def shell(serial: str, args: List[str], timeout: int = 10) -> str:
        serial = AdbManager._normalize_serial(serial)
        res = AdbManager._run_cmd(["adb", "-s", serial, "shell", *args], timeout=timeout)
        return (res.stdout or res.stderr or "").strip()

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
            cmd = AdbManager._apply_adb_server(cmd)
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
    def _run_cmd(cmd: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
        """
        Executes a shell command with a timeout and captures the output.

        Args:
            cmd (List[str]): The command to execute as a list of strings.
            timeout (int, optional): Maximum time in seconds to wait for command completion. Defaults to 10.

        Returns:
            subprocess.CompletedProcess: The result of the executed command.
        """
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()  # type: ignore
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore

        try:
            cmd = AdbManager._apply_adb_server(cmd)
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                check=False,
                timeout=timeout,
            )
        except Exception as e:
            return subprocess.CompletedProcess(cmd, -1, "", str(e))

    @staticmethod
    def get_devices_detailed() -> List[Dict[str, str]]:
        """
        Retrieves a list of connected devices with details.

        Returns:
            List[Dict[str, str]]: A list of dictionaries, each containing 'serial' and 'model' keys.
        """
        try:
            AdbManager._run_cmd(['adb', 'start-server'])
            res = AdbManager._run_cmd(['adb', 'devices', '-l'])
            lines = (res.stdout or "").strip().split('\n')[1:]
            devices: List[Dict[str, str]] = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    serial = AdbManager._normalize_serial(parts[0])
                    state = parts[1]
                    details = {"serial": serial, "model": "Unknown", "state": state}
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
        serial = AdbManager._normalize_serial(serial)
        # -p is essential for PNG format
        best_bytes: Optional[bytes] = None
        best_len = 0
        best_id = None

        # If user selected a display, try it first
        preferred_id = AdbManager._preferred_display_id.get(serial) or AdbManager._best_display_id.get(serial)
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
        serial = AdbManager._normalize_serial(serial)
        if serial in AdbManager._display_ids_cache:
            return AdbManager._display_ids_cache[serial]

        ids: List[str] = []

        res_cmd = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'cmd', 'display', 'list-displays'], timeout=8)
        if res_cmd and res_cmd.stdout:
            for line in res_cmd.stdout.splitlines():
                line = line.strip()
                if line.startswith("Display "):
                    parts = line.split(":", 1)[0].split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        ids.append(parts[1])

        if not ids:
            res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'display'], timeout=10)
            if res and res.stdout:
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("mDisplayId="):
                        disp_id = line.split("=", 1)[1].strip()
                        if disp_id.isdigit():
                            ids.append(disp_id)
                    if line.startswith("Display "):
                        parts = line.split(":", 1)[0].split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            ids.append(parts[1])

        if not ids:
            res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'SurfaceFlinger', '--display-id'], timeout=10)
            if res and res.stdout:
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("Display ") or line.startswith("Virtual Display "):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            ids.append(parts[1])

        ids = list(dict.fromkeys(ids))
        AdbManager._display_ids_cache[serial] = ids
        return ids

    @staticmethod
    def get_display_details(serial: str) -> List[Dict[str, str]]:
        serial = AdbManager._normalize_serial(serial)
        details: List[Dict[str, str]] = []

        res_cmd = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'cmd', 'display', 'list-displays'], timeout=8)
        if res_cmd and res_cmd.stdout:
            for line in res_cmd.stdout.splitlines():
                line = line.strip()
                if line.startswith("Display "):
                    prefix, rest = line.split(":", 1)
                    parts = prefix.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        disp_id = parts[1]
                        details.append({"id": disp_id, "label": rest.strip()})

        if details:
            return details

        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'display'], timeout=10)
        if res and res.stdout:
            current_id = None
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("Display "):
                    parts = line.split(":", 1)[0].split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        current_id = parts[1]
                        details.append({"id": current_id, "label": ""})
                if current_id and "DisplayDeviceInfo{" in line:
                    name = ""
                    if line.startswith("DisplayDeviceInfo{\""):
                        try:
                            name = line.split("DisplayDeviceInfo{\"", 1)[1].split("\"", 1)[0]
                        except Exception:
                            name = ""
                    size = ""
                    try:
                        parts = line.split("DisplayDeviceInfo{", 1)[1]
                        dims = [p for p in parts.split(",") if " x " in p]
                        if dims:
                            size = dims[0].strip()
                    except Exception:
                        size = ""
                    label = ""
                    if name:
                        label = name
                    if size:
                        label = f"{label} {size}".strip()
                    for item in details:
                        if item.get("id") == current_id and not item.get("label"):
                            item["label"] = label or line
                            break
        return details

    @staticmethod
    def get_power_summary(serial: str) -> Dict[str, str]:
        serial = AdbManager._normalize_serial(serial)
        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'power'], timeout=8)
        wakefulness = "Unknown"
        interactive = "Unknown"
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("mWakefulness="):
                wakefulness = line.split("=", 1)[1]
            if line.startswith("mInteractive="):
                interactive = line.split("=", 1)[1]
            if line.startswith("interactive="):
                interactive = line.split("=", 1)[1]
        return {"wakefulness": wakefulness, "interactive": interactive}

    @staticmethod
    def get_display_summary(serial: str) -> List[str]:
        serial = AdbManager._normalize_serial(serial)
        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'display'], timeout=10)
        summaries: List[str] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("DisplayDeviceInfo{"):
                summaries.append(line)
        return summaries

    @staticmethod
    def get_device_meta(serial: str) -> Dict[str, Any]:
        serial = AdbManager._normalize_serial(serial)
        now = int(time.time())
        model = AdbManager.getprop(serial, "ro.product.model")
        serialno = AdbManager.getprop(serial, "ro.serialno")
        ro_secure = AdbManager.getprop(serial, "ro.secure")
        display_ids = AdbManager.get_display_ids(serial)
        display_info = AdbManager.get_display_summary(serial)
        power = AdbManager.get_power_summary(serial)
        return {
            "timestamp": now,
            "serial": serial,
            "serialno": serialno,
            "model": model,
            "ro_secure": ro_secure,
            "display_ids": display_ids,
            "display_info": display_info,
            "preferred_display_id": AdbManager._preferred_display_id.get(serial),
            "power": power,
        }

    @staticmethod
    def set_preferred_display_id(serial: str, display_id: Optional[str]) -> None:
        serial = AdbManager._normalize_serial(serial)
        if display_id:
            AdbManager._preferred_display_id[serial] = display_id
        else:
            AdbManager._preferred_display_id.pop(serial, None)

    @staticmethod
    def get_preferred_display_id(serial: str) -> Optional[str]:
        serial = AdbManager._normalize_serial(serial)
        return AdbManager._preferred_display_id.get(serial)

    @staticmethod
    def get_surfaceflinger_layers(serial: str) -> List[Dict[str, Any]]:
        """
        Attempts to enumerate SurfaceFlinger layers and flag secure layers when possible.
        Returns a list of dicts: {name, secure}.
        """
        layers: List[Dict[str, Any]] = []
        try:
            serial = AdbManager._normalize_serial(serial)
            list_res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'SurfaceFlinger', '--list'], timeout=10)
            names = [l.strip() for l in (list_res.stdout or "").splitlines() if l.strip()]
            layer_map = {n: {"name": n, "secure": False} for n in names}

            # Parse --layers for Secure flags (best effort)
            layers_res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'SurfaceFlinger', '--layers'], timeout=12)
            current_name: Optional[str] = None
            for line in (layers_res.stdout or "").splitlines():
                line = line.strip()
                if line.startswith("Layer ") and "(" in line and ")" in line:
                    try:
                        current_name = line.split("(", 1)[1].rsplit(")", 1)[0].strip()
                    except Exception:
                        current_name = None
                if current_name and line.startswith("Flags:") and "Secure" in line:
                    if current_name in layer_map:
                        layer_map[current_name]["secure"] = True
            layers = list(layer_map.values())
        except Exception:
            return []
        return layers

    @staticmethod
    def get_xml_dump(serial: str, display_id: Optional[str] = None) -> Optional[str]:
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

        serial = AdbManager._normalize_serial(serial)
        AdbManager._last_dump_error = None
        service_available = AdbManager.has_uiautomator_service(serial)
        if not service_available:
            AdbManager._last_dump_error = "uiautomator service not listed; attempting dump anyway"
        preferred = display_id or AdbManager._preferred_display_id.get(serial)
        display_candidates: List[Optional[str]] = []
        if preferred:
            display_candidates.append(str(preferred))
        display_candidates.append(None)
        for disp in AdbManager.get_display_ids(serial):
            if disp and disp != preferred:
                display_candidates.append(str(disp))

        def read_existing() -> Optional[str]:
            check = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'du', '-b', temp_path])
            size = 0
            try:
                size = int((check.stdout or "").split()[0])
            except (IndexError, ValueError):
                size = 0
            if size >= 200:
                res_cat = AdbManager._run_cmd(['adb', '-s', serial, 'exec-out', 'cat', temp_path])
                xml = (res_cat.stdout or "").strip()
                if xml and "<hierarchy" in xml:
                    return xml
            return None

        existing_xml = read_existing()

        def try_dump(disp: Optional[str], compressed: bool) -> Optional[str]:
            # Delete old first to ensure we don't read stale data (unless service missing)
            if service_available:
                AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'rm', temp_path])

            dump_cmd = ['adb', '-s', serial, 'shell', 'uiautomator', 'dump']
            if compressed:
                dump_cmd += ['--compressed']
            if disp:
                dump_cmd += ['--display-id', str(disp)]
            dump_cmd += [temp_path]
            res = AdbManager._run_cmd(dump_cmd, timeout=20)
            out = ((res.stdout or "") + (res.stderr or "")).lower()
            if res.returncode and res.returncode != 0:
                if res.returncode == 137:
                    AdbManager._last_dump_error = "uiautomator dump was killed by device (exit 137)"
                else:
                    AdbManager._last_dump_error = f"uiautomator dump failed (code {res.returncode})"
            if "killed" in out:
                AdbManager._last_dump_error = "uiautomator dump was killed by device"

            check = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'du', '-b', temp_path])
            size = 0
            try:
                size = int((check.stdout or "").split()[0])
            except (IndexError, ValueError):
                size = 0

            if size >= 200:
                res_cat = AdbManager._run_cmd(['adb', '-s', serial, 'exec-out', 'cat', temp_path])
                xml = (res_cat.stdout or "").strip()
                if xml and "<hierarchy" in xml:
                    return xml
            return None

        def try_direct(disp: Optional[str], compressed: bool) -> Optional[str]:
            direct_cmd = ['adb', '-s', serial, 'exec-out', 'uiautomator', 'dump']
            if compressed:
                direct_cmd += ['--compressed']
            if disp:
                direct_cmd += ['--display-id', str(disp)]
            direct_cmd += ['/dev/tty']
            res_direct = AdbManager._run_cmd(direct_cmd, timeout=20)
            out = ((res_direct.stdout or "") + (res_direct.stderr or "")).lower()
            if res_direct.returncode and res_direct.returncode != 0:
                if res_direct.returncode == 137:
                    AdbManager._last_dump_error = "uiautomator dump was killed by device (exit 137)"
                else:
                    AdbManager._last_dump_error = f"uiautomator dump failed (code {res_direct.returncode})"
            if "killed" in out:
                AdbManager._last_dump_error = "uiautomator dump was killed by device"
            xml = (res_direct.stdout or "").strip()
            if xml and "<hierarchy" in xml:
                return xml
            return None

        def try_cmd_dump(disp: Optional[str], compressed: bool) -> Optional[str]:
            AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'rm', temp_path])
            cmd = ['adb', '-s', serial, 'shell', 'cmd', 'uiautomator', 'dump']
            if compressed:
                cmd += ['--compressed']
            if disp:
                cmd += ['--display-id', str(disp)]
            cmd += [temp_path]
            res = AdbManager._run_cmd(cmd, timeout=20)
            out = ((res.stdout or "") + (res.stderr or "")).lower()
            if res.returncode and res.returncode != 0:
                if res.returncode == 137:
                    AdbManager._last_dump_error = "cmd uiautomator dump was killed by device (exit 137)"
                else:
                    AdbManager._last_dump_error = f"cmd uiautomator dump failed (code {res.returncode})"
            if "killed" in out:
                AdbManager._last_dump_error = "cmd uiautomator dump was killed by device"

            check = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'du', '-b', temp_path])
            size = 0
            try:
                size = int((check.stdout or "").split()[0])
            except (IndexError, ValueError):
                size = 0
            if size >= 200:
                res_cat = AdbManager._run_cmd(['adb', '-s', serial, 'exec-out', 'cat', temp_path])
                xml = (res_cat.stdout or "").strip()
                if xml and "<hierarchy" in xml:
                    return xml
            return None

        for disp in display_candidates:
            for compressed in (True, False):
                for _ in range(2):
                    xml = try_dump(disp, compressed)
                    if xml:
                        return xml
                    time.sleep(0.4)
                xml = try_direct(disp, compressed)
                if xml:
                    return xml
                xml = try_cmd_dump(disp, compressed)
                if xml:
                    return xml

        if not AdbManager._last_dump_error:
            AdbManager._last_dump_error = "uiautomator returned no hierarchy"
        if existing_xml:
            AdbManager._last_dump_error = "using existing /sdcard/window_dump.xml (may be stale)"
            return existing_xml
        return None

    @staticmethod
    def get_last_dump_error() -> Optional[str]:
        return AdbManager._last_dump_error

    @staticmethod
    def is_adb_root(serial: str) -> bool:
        serial = AdbManager._normalize_serial(serial)
        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'id'], timeout=6)
        text = (res.stdout or "") + (res.stderr or "")
        return "uid=0" in text

    @staticmethod
    def adb_root(serial: str) -> tuple[bool, str]:
        serial = AdbManager._normalize_serial(serial)
        res = AdbManager._run_cmd(['adb', '-s', serial, 'root'], timeout=10)
        text = ((res.stdout or "") + (res.stderr or "")).strip()
        lower = text.lower()
        if "cannot run as root" in lower:
            return (False, text or "adbd cannot run as root on this build")
        if "already running as root" in lower:
            return (True, text or "adbd already running as root")
        if "restarting adbd as root" in lower:
            return (True, text or "adbd restarting as root")
        if res.returncode == 0:
            return (True, text or "adb root command completed")
        return (False, text or f"adb root failed (code {res.returncode})")

    @staticmethod
    def has_uiautomator_service(serial: str) -> bool:
        serial = AdbManager._normalize_serial(serial)
        if serial in AdbManager._uiautomator_service_cache:
            return AdbManager._uiautomator_service_cache[serial]
        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'service', 'list'], timeout=6)
        text = (res.stdout or "") + (res.stderr or "")
        available = "uiautomator" in text.lower()
        AdbManager._uiautomator_service_cache[serial] = available
        return available

    @staticmethod
    def get_screen_size(serial: str) -> Optional[tuple[int, int]]:
        serial = AdbManager._normalize_serial(serial)
        if serial in AdbManager._display_size_cache:
            return AdbManager._display_size_cache[serial]

        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'wm', 'size'], timeout=6)
        text = (res.stdout or "") + (res.stderr or "")
        match = re.search(r"Physical size:\s*(\d+)x(\d+)", text)
        if not match:
            match = re.search(r"Override size:\s*(\d+)x(\d+)", text)
        if match:
            w, h = int(match.group(1)), int(match.group(2))
            AdbManager._display_size_cache[serial] = (w, h)
            return (w, h)

        res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'display'], timeout=8)
        text = (res.stdout or "")
        match = re.search(r"real\s*(\d+)\s*x\s*(\d+)", text)
        if match:
            w, h = int(match.group(1)), int(match.group(2))
            AdbManager._display_size_cache[serial] = (w, h)
            return (w, h)
        return None

    @staticmethod
    def get_current_focus(serial: str) -> str:
        """
        Retrieves the name of the currently focused window/activity.
        """
        try:
            # dumpsys window displays
            serial = AdbManager._normalize_serial(serial)
            cmd = ['adb', '-s', serial, 'shell', 'dumpsys', 'window', 'windows']
            res = AdbManager._run_cmd(cmd)
            for line in res.stdout.split('\n'):
                if 'mCurrentFocus' in line or 'mFocusedApp' in line:
                    return line.strip()
            res2 = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'activity', 'top'])
            for line in res2.stdout.split('\n'):
                if 'mResumedActivity' in line or 'mFocusedActivity' in line or 'ResumedActivity' in line:
                    return line.strip()
            res3 = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'dumpsys', 'activity', 'activities'])
            for line in res3.stdout.split('\n'):
                if 'mResumedActivity' in line or 'mFocusedActivity' in line or 'ResumedActivity' in line:
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
        serial = AdbManager._normalize_serial(serial)
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
        serial = AdbManager._normalize_serial(serial)
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
        serial = AdbManager._normalize_serial(serial)
        if not os.path.exists(folder): 
            os.makedirs(folder)
        
        png_bytes = None
        for _ in range(3):
            png_bytes = AdbManager.get_screenshot_bytes(serial)
            if png_bytes:
                break
            res = AdbManager._run_bytes_cmd(['adb', '-s', serial, 'exec-out', 'screencap', '-p'])
            if res and res.returncode == 0 and res.stdout:
                png_bytes = res.stdout
                break
            time.sleep(0.4)
        if png_bytes:
            with open(os.path.join(folder, 'screenshot.png'), 'wb') as f: 
                f.write(png_bytes)

        xml_str = AdbManager.get_xml_dump(serial, AdbManager.get_preferred_display_id(serial))
        with open(os.path.join(folder, 'dump.uix'), 'w', encoding='utf-8') as f:
            if xml_str: 
                f.write(xml_str)
            else: 
                f.write("<error>Failed to capture dump</error>")

        res = AdbManager._run_cmd(['adb', '-s', serial, 'logcat', '-d', '-t', '500'])
        with open(os.path.join(folder, 'logcat.txt'), 'w', encoding='utf-8') as f: 
            f.write(res.stdout)

        res_all = AdbManager._run_cmd(['adb', '-s', serial, 'logcat', '-b', 'all', '-d'])
        with open(os.path.join(folder, 'logcat_all.txt'), 'w', encoding='utf-8', errors='replace') as f:
            f.write(res_all.stdout or res_all.stderr or "")

        focus = AdbManager.get_current_focus(serial)
        with open(os.path.join(folder, 'focus.txt'), 'w', encoding='utf-8') as f:
            f.write(focus)

        meta = AdbManager.get_device_meta(serial)
        meta["focus"] = focus
        with open(os.path.join(folder, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)

        AdbManager._capture_dumpsys(serial, folder)
        AdbManager._capture_bugreport(serial, folder)

    @staticmethod
    def _capture_dumpsys(serial: str, folder: str) -> None:
        focus = AdbManager.get_current_focus(serial)
        pkg = ""
        try:
            import re

            match = re.search(r"\s([\w\.]+)/[^\s}]+", focus)
            if match:
                pkg = match.group(1)
        except Exception:
            pkg = ""

        dumpsys_targets = {
            "dumpsys_window_windows.txt": ['dumpsys', 'window', 'windows'],
            "dumpsys_window_displays.txt": ['dumpsys', 'window', 'displays'],
            "dumpsys_window_all.txt": ['dumpsys', 'window', '-a'],
            "dumpsys_activity_top.txt": ['dumpsys', 'activity', 'top'],
            "dumpsys_activity_activities.txt": ['dumpsys', 'activity', 'activities'],
            "dumpsys_activity_recents.txt": ['dumpsys', 'activity', 'recents'],
            "dumpsys_activity_processes.txt": ['dumpsys', 'activity', 'processes'],
            "dumpsys_display.txt": ['dumpsys', 'display'],
            "dumpsys_power.txt": ['dumpsys', 'power'],
            "dumpsys_input.txt": ['dumpsys', 'input'],
            "dumpsys_surfaceflinger_list.txt": ['dumpsys', 'SurfaceFlinger', '--list'],
            "dumpsys_surfaceflinger_layers.txt": ['dumpsys', 'SurfaceFlinger', '--layers'],
            "dumpsys_media_audio_flinger.txt": ['dumpsys', 'media.audio_flinger'],
        }

        if pkg:
            dumpsys_targets["dumpsys_gfxinfo_pkg.txt"] = ['dumpsys', 'gfxinfo', pkg]
            dumpsys_targets["dumpsys_meminfo_pkg.txt"] = ['dumpsys', 'meminfo', pkg]

        for filename, args in dumpsys_targets.items():
            try:
                res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', *args], timeout=20)
                with open(os.path.join(folder, filename), 'w', encoding='utf-8', errors='replace') as f:
                    f.write(res.stdout or res.stderr or "")
            except Exception:
                continue

        try:
            res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'getevent', '-lp'], timeout=20)
            with open(os.path.join(folder, 'getevent_lp.txt'), 'w', encoding='utf-8', errors='replace') as f:
                f.write(res.stdout or res.stderr or "")
        except Exception:
            pass

        try:
            res = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'getprop'], timeout=20)
            with open(os.path.join(folder, 'getprop.txt'), 'w', encoding='utf-8', errors='replace') as f:
                f.write(res.stdout or res.stderr or "")
        except Exception:
            pass

    @staticmethod
    def _capture_bugreport(serial: str, folder: str) -> None:
        try:
            res = AdbManager._run_cmd(['adb', '-s', serial, 'bugreport'], timeout=120)
            out = res.stdout or res.stderr or ""
            if out.strip():
                with open(os.path.join(folder, 'bugreport.txt'), 'w', encoding='utf-8', errors='replace') as f:
                    f.write(out)
        except Exception:
            pass
