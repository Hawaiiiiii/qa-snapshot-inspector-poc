"""
ADB Manager Module.

This module provides a robust interface for interacting with Android devices via the
Android Debug Bridge (ADB). It handles device discovery, screen capture, UI automation
dumps, and logcat retrieval with error handling and platform-specific adjustments.
"""

import subprocess
import os
from typing import List, Dict, Optional, Any

class AdbManager:
    """
    Static utility class for ADB operations.
    """

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
    def get_screenshot_bytes(serial: str) -> Optional[bytes]:
        """
        Captures a screenshot from the specified device as raw PNG bytes.

        Args:
            serial (str): The device serial number.

        Returns:
            Optional[bytes]: The PNG image data, or None if capture failed.
        """
        # -p is essential for PNG format
        cmd = ['adb', '-s', serial, 'exec-out', 'screencap', '-p']
        res = AdbManager._run_bytes_cmd(cmd)
        if res and res.returncode == 0:
            return res.stdout
        return None

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
