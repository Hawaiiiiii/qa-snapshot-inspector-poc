# Safe playbook for rack/ADB capture (PowerShell)
# Usage: .\scripts\safe_playbook.ps1 -Serial "<serial>" -OutDir ".\captures"
param(
    [string]$Serial = "",
    [string]$OutDir = ".\captures",
    [long[]]$DisplayIds = @(0,1,2,3,4,5)
)

$ErrorActionPreference = "SilentlyContinue"

function Run-Adb($args) {
    if ([string]::IsNullOrWhiteSpace($Serial)) {
        return & adb @args
    }
    return & adb -s $Serial @args
}

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

"[ADB] Devices:" | Write-Output
& adb devices -l | Write-Output

"[ADB] Power state:" | Write-Output
Run-Adb @("shell","dumpsys","power") | Select-String -Pattern "mInteractive|mWakefulness" | Write-Output

"[ADB] SurfaceFlinger display IDs:" | Write-Output
Run-Adb @("shell","dumpsys","SurfaceFlinger","--display-id") | Write-Output

"[ADB] Display state:" | Write-Output
Run-Adb @("shell","dumpsys","display") | Select-String -Pattern "mState|state" | Write-Output

"[ADB] Wake + unlock:" | Write-Output
Run-Adb @("shell","input","keyevent","26") | Out-Null
Run-Adb @("shell","input","keyevent","82") | Out-Null
Run-Adb @("shell","svc","power","stayon","true") | Out-Null

"[ADB] Try uiautomator dump:" | Write-Output
Run-Adb @("shell","uiautomator","dump","/sdcard/dump.uix") | Write-Output
Run-Adb @("pull","/sdcard/dump.uix",(Join-Path $OutDir "dump.uix")) | Write-Output

"[ADB] Multi-display screenshots:" | Write-Output
foreach ($id in $DisplayIds) {
    $remote = "/sdcard/cap${id}.png"
    $local = Join-Path $OutDir ("cap{0}.png" -f $id)
    Run-Adb @("shell","screencap","-d",$id,"-p",$remote) | Out-Null
    Run-Adb @("pull",$remote,$local) | Write-Output
    if (Test-Path $local) {
        $size = (Get-Item $local).Length
        if ($size -le 0) {
            "[WARN] cap${id}.png is empty (0 bytes)." | Write-Output
        } else {
            "[OK] cap${id}.png size: $size bytes" | Write-Output
        }
    }
}

"[ADB] Standard screenshot:" | Write-Output
Run-Adb @("shell","screencap","-p","/sdcard/cap.png") | Out-Null
Run-Adb @("pull","/sdcard/cap.png",(Join-Path $OutDir "cap.png")) | Write-Output
if (Test-Path (Join-Path $OutDir "cap.png")) {
    $size = (Get-Item (Join-Path $OutDir "cap.png")).Length
    if ($size -le 0) {
        "[WARN] cap.png is empty (0 bytes)." | Write-Output
    } else {
        "[OK] cap.png size: $size bytes" | Write-Output
    }
}

"[DONE] Outputs in $OutDir" | Write-Output
