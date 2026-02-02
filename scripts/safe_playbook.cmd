@echo off
setlocal

REM Usage: scripts\safe_playbook.cmd <serial> <outdir>
set SERIAL=%~1
set OUTDIR=%~2
if "%OUTDIR%"=="" set OUTDIR=captures
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

if "%SERIAL%"=="" (
  set ADB=adb
) else (
  set ADB=adb -s %SERIAL%
)

echo [ADB] Devices:
adb devices -l

echo [ADB] Wake + unlock:
%ADB% shell input keyevent 26
%ADB% shell input keyevent 82
%ADB% shell svc power stayon true

echo [ADB] Try uiautomator dump:
%ADB% shell uiautomator dump /sdcard/dump.uix
%ADB% pull /sdcard/dump.uix "%OUTDIR%\dump.uix"

echo [ADB] Multi-display screenshots:
for %%D in (0 1 2 3 4 5) do (
  %ADB% shell screencap -d %%D -p /sdcard/cap%%D.png
  %ADB% pull /sdcard/cap%%D.png "%OUTDIR%\cap%%D.png"
)

echo [ADB] Standard screenshot:
%ADB% shell screencap -p /sdcard/cap.png
%ADB% pull /sdcard/cap.png "%OUTDIR%\cap.png"

echo [DONE] Outputs in %OUTDIR%
endlocal
