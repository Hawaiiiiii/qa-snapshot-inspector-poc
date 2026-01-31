import subprocess
import os
import time
import json
import xml.dom.minidom

class AdbManager:
    @staticmethod
    def _run_cmd(cmd, timeout=10):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', 
                                 startupinfo=startupinfo, check=False, timeout=timeout)
            return res
        except Exception as e:
            return subprocess.CompletedProcess(cmd, -1, "", str(e))

    @staticmethod
    def _run_bytes_cmd(cmd):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            return subprocess.run(cmd, capture_output=True, startupinfo=startupinfo, check=False, timeout=5)
        except: return None

    @staticmethod
    def get_devices_detailed():
        try:
            res = AdbManager._run_cmd(['adb', 'devices', '-l'])
            lines = res.stdout.strip().split('\n')[1:] 
            devices = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    details = {"serial": parts[0], "model": "Unknown"}
                    for p in parts[2:]:
                        if "model:" in p: details["model"] = p.split(":")[1]
                    devices.append(details)
            return devices
        except: return []

    @staticmethod
    def get_screenshot_bytes(serial):
        # -p is essential for PNG format
        cmd = ['adb', '-s', serial, 'exec-out', 'screencap', '-p']
        res = AdbManager._run_bytes_cmd(cmd)
        if res and res.returncode == 0:
            return res.stdout
        return None

    @staticmethod
    def get_xml_dump(serial):
        """ Robust dump with retry for partial trees """
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Strategy 1: Fast Pipe (often fails on complex BMW UI)
        # res = AdbManager._run_cmd(['adb', '-s', serial, 'exec-out', 'uiautomator', 'dump', '/dev/tty'])
        # if "</hierarchy>" in res.stdout and len(res.stdout) > 500:
        #    return res.stdout
        
        # Strategy 2: File based (Slow but Reliable) - The "Holy Water" method
        temp_path = "/sdcard/window_dump.xml"
        
        # Delete old first to ensure we don't read stale data
        AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'rm', temp_path])
        
        # Dump
        AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'uiautomator', 'dump', temp_path], timeout=15)
        
        # Check size (if it's small, it failed or captured only root)
        check = AdbManager._run_cmd(['adb', '-s', serial, 'shell', 'du', '-b', temp_path])
        try:
            size = int(check.stdout.split()[0])
            if size < 200: return None # Trash dump
        except: pass

        # Pull
        res_cat = AdbManager._run_cmd(['adb', '-s', serial, 'exec-out', 'cat', temp_path])
        return res_cat.stdout

    @staticmethod
    def tap(serial, x, y):
        subprocess.Popen(['adb', '-s', serial, 'shell', 'input', 'tap', str(x), str(y)], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def capture_snapshot(serial, folder):
        if not os.path.exists(folder): os.makedirs(folder)
        
        png_bytes = AdbManager.get_screenshot_bytes(serial)
        if png_bytes:
            with open(os.path.join(folder, 'screenshot.png'), 'wb') as f: f.write(png_bytes)

        xml_str = AdbManager.get_xml_dump(serial)
        with open(os.path.join(folder, 'dump.uix'), 'w', encoding='utf-8') as f:
            if xml_str: f.write(xml_str)
            else: f.write("<error>Failed to capture dump</error>")

        res = AdbManager._run_cmd(['adb', '-s', serial, 'logcat', '-d', '-t', '500'])
        with open(os.path.join(folder, 'logcat.txt'), 'w', encoding='utf-8') as f: f.write(res.stdout)