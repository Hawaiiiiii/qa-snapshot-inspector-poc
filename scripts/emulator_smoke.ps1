param(
    [Parameter(Mandatory = $true)]
    [string]$Serial,
    [string]$OutputRoot = "docs\\evidence\\emulator",
    [string]$ScrcpyPath = "",
    [int]$ScrcpySmokeSeconds = 8
)

$ErrorActionPreference = 'Stop'

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $OutputRoot ("smoke_" + $Serial.Replace(':','_') + "_" + $timestamp)
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$report = [ordered]@{
    schema = "quantum_emulator_smoke.v1"
    generated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    serial = $Serial
    output_dir = (Resolve-Path $outDir).Path
    checks = [ordered]@{
        adb_devices = [ordered]@{ pass = $false; note = ""; file = "adb_devices.txt" }
        uia_dump = [ordered]@{ pass = $false; note = ""; file = "uia_dump.txt" }
        uia_pull = [ordered]@{ pass = $false; note = ""; file = "ui.xml" }
        screencap = [ordered]@{ pass = $false; note = ""; file = "screen.png" }
        scrcpy = [ordered]@{ pass = $false; note = ""; file = "scrcpy_smoke.txt" }
    }
}

$adbDevicesPath = Join-Path $outDir "adb_devices.txt"
try {
    $adbOutput = & adb devices -l 2>&1
    $adbOutput | Set-Content -Path $adbDevicesPath -Encoding UTF8
    if ($adbOutput -match [Regex]::Escape($Serial)) {
        $report.checks.adb_devices.pass = $true
        $report.checks.adb_devices.note = "serial found in adb devices -l"
    } else {
        $report.checks.adb_devices.note = "serial not found in adb devices -l"
    }
} catch {
    $report.checks.adb_devices.note = "adb devices failed: $($_.Exception.Message)"
}

$uiaDumpPath = Join-Path $outDir "uia_dump.txt"
try {
    $uiaOut = & adb -s $Serial shell uiautomator dump /sdcard/ui.xml 2>&1
    $uiaOut | Set-Content -Path $uiaDumpPath -Encoding UTF8
    if (($uiaOut -join "`n") -match "UI hierchary dumped|UI hierarchy dumped") {
        $report.checks.uia_dump.pass = $true
        $report.checks.uia_dump.note = "uiautomator dump succeeded"
    } else {
        $report.checks.uia_dump.note = "uiautomator dump did not report success"
    }
} catch {
    $report.checks.uia_dump.note = "uiautomator dump failed: $($_.Exception.Message)"
}

$uiXmlPath = Join-Path $outDir "ui.xml"
try {
    $pullOut = & adb -s $Serial pull /sdcard/ui.xml $uiXmlPath 2>&1
    $pullOut | Set-Content -Path (Join-Path $outDir "uia_pull.txt") -Encoding UTF8
    if ((Test-Path $uiXmlPath) -and ((Get-Item $uiXmlPath).Length -gt 0)) {
        $report.checks.uia_pull.pass = $true
        $report.checks.uia_pull.note = "pulled ui.xml"
    } else {
        $report.checks.uia_pull.note = "ui.xml missing or empty"
    }
} catch {
    $report.checks.uia_pull.note = "uia pull failed: $($_.Exception.Message)"
}

$screenPath = Join-Path $outDir "screen.png"
try {
    cmd /c "adb -s $Serial exec-out screencap -p > \"$screenPath\""
    if ((Test-Path $screenPath) -and ((Get-Item $screenPath).Length -gt 0)) {
        $report.checks.screencap.pass = $true
        $report.checks.screencap.note = "screencap wrote PNG"
    } else {
        $report.checks.screencap.note = "screen.png missing or empty"
    }
} catch {
    $report.checks.screencap.note = "screencap failed: $($_.Exception.Message)"
}

$scrcpyExe = $ScrcpyPath
if (-not $scrcpyExe) {
    $cmd = Get-Command scrcpy -ErrorAction SilentlyContinue
    if ($cmd) { $scrcpyExe = $cmd.Source }
}

$scrcpyLog = Join-Path $outDir "scrcpy_smoke.txt"
if (-not $scrcpyExe) {
    $report.checks.scrcpy.note = "scrcpy not found in PATH and no --ScrcpyPath provided"
    "scrcpy executable not found" | Set-Content -Path $scrcpyLog -Encoding UTF8
} else {
    try {
        $proc = Start-Process -FilePath $scrcpyExe -ArgumentList @("-s", $Serial, "--no-audio", "--no-control", "--window-x", "-32000", "--window-y", "-32000") -PassThru -WindowStyle Hidden
        Start-Sleep -Seconds ([Math]::Max(3, $ScrcpySmokeSeconds))
        if (-not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force
            $report.checks.scrcpy.pass = $true
            $report.checks.scrcpy.note = "scrcpy started and stayed alive during smoke window"
        } elseif ($proc.ExitCode -eq 0) {
            $report.checks.scrcpy.pass = $true
            $report.checks.scrcpy.note = "scrcpy started and exited cleanly"
        } else {
            $report.checks.scrcpy.note = "scrcpy exited early with code $($proc.ExitCode)"
        }
        "scrcpy exe: $scrcpyExe`nexit code: $($proc.ExitCode)" | Set-Content -Path $scrcpyLog -Encoding UTF8
    } catch {
        $report.checks.scrcpy.note = "scrcpy launch failed: $($_.Exception.Message)"
        $_ | Out-String | Set-Content -Path $scrcpyLog -Encoding UTF8
    }
}

$reportPath = Join-Path $outDir "emulator_smoke_report.json"
$report | ConvertTo-Json -Depth 8 | Set-Content -Path $reportPath -Encoding UTF8

$allPass = $true
foreach ($name in $report.checks.Keys) {
    if (-not $report.checks[$name].pass) {
        $allPass = $false
    }
}

Write-Host ($report | ConvertTo-Json -Depth 8)
if (-not $allPass) {
    exit 2
}
exit 0
