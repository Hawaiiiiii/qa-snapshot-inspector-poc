param(
    [string]$Hu = "169.254.166.99:5555",
    [string]$Cde = "169.254.166.167:5555",
    [string]$Rse = "169.254.166.152:5555",
    [string]$OutputRoot = "docs\\evidence\\rack",
    [int]$ScrcpySmokeSeconds = 6,
    [switch]$SkipScrcpy = $false
)

$ErrorActionPreference = 'Stop'

function Find-PngOffset([byte[]]$Data) {
    if (-not $Data -or $Data.Length -lt 8) { return -1 }
    for ($i = 0; $i -le ($Data.Length - 8); $i++) {
        if ($Data[$i] -eq 0x89 -and $Data[$i + 1] -eq 0x50 -and $Data[$i + 2] -eq 0x4E -and $Data[$i + 3] -eq 0x47 -and $Data[$i + 4] -eq 0x0D -and $Data[$i + 5] -eq 0x0A -and $Data[$i + 6] -eq 0x1A -and $Data[$i + 7] -eq 0x0A) {
            return $i
        }
    }
    return -1
}

function Normalize-PngFile([string]$Path) {
    if (-not (Test-Path $Path)) { return @{ pass = $false; note = "file missing" } }
    [byte[]]$bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -eq 0) { return @{ pass = $false; note = "file empty" } }
    $offset = Find-PngOffset -Data $bytes
    if ($offset -lt 0) { return @{ pass = $false; note = "PNG header not found in capture output" } }
    if ($offset -gt 0) {
        [byte[]]$trimmed = $bytes[$offset..($bytes.Length - 1)]
        [System.IO.File]::WriteAllBytes($Path, $trimmed)
        return @{ pass = $true; note = "PNG recovered after prefix bytes (offset=$offset)" }
    }
    return @{ pass = $true; note = "PNG header valid" }
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $OutputRoot ("g70_multidevice_" + $timestamp)
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

$targets = @(
    @{ role = "hu"; serial = $Hu },
    @{ role = "cde"; serial = $Cde },
    @{ role = "rse"; serial = $Rse }
)

$scrcpyExe = ""
if (-not $SkipScrcpy) {
    $cmd = Get-Command scrcpy -ErrorAction SilentlyContinue
    if ($cmd) { $scrcpyExe = $cmd.Source }
}

function Test-Target([string]$role, [string]$serial) {
    $deviceDir = Join-Path $outDir $role
    New-Item -ItemType Directory -Path $deviceDir -Force | Out-Null

    $checks = [ordered]@{
        adb_connect = [ordered]@{ pass = $false; note = ""; file = "adb_connect.txt" }
        adb_state = [ordered]@{ pass = $false; note = ""; file = "adb_state.txt" }
        model = [ordered]@{ pass = $false; note = ""; file = "model.txt" }
        uia_dump = [ordered]@{ pass = $false; note = ""; file = "uia_dump.txt" }
        uia_pull = [ordered]@{ pass = $false; note = ""; file = "window_dump.xml" }
        screencap = [ordered]@{ pass = $false; note = ""; file = "screen.png" }
        scrcpy = [ordered]@{ pass = $false; note = ""; file = "scrcpy.txt" }
    }

    $connectFile = Join-Path $deviceDir "adb_connect.txt"
    $stateFile = Join-Path $deviceDir "adb_state.txt"
    $modelFile = Join-Path $deviceDir "model.txt"
    $uiaFile = Join-Path $deviceDir "uia_dump.txt"
    $pullFile = Join-Path $deviceDir "window_dump.xml"
    $screencapFile = Join-Path $deviceDir "screen.png"
    $scrcpyFile = Join-Path $deviceDir "scrcpy.txt"

    try {
        $connectOut = & adb connect $serial 2>&1
        ($connectOut | Out-String) | Set-Content -Path $connectFile -Encoding UTF8
        $txt = ($connectOut -join "`n")
        if ($txt -match "connected to|already connected to") {
            $checks.adb_connect.pass = $true
            $checks.adb_connect.note = "adb connect succeeded"
        } else {
            $checks.adb_connect.note = "adb connect did not report success"
        }
    } catch {
        $checks.adb_connect.note = "adb connect failed: $($_.Exception.Message)"
    }

    try {
        $stateOut = & adb -s $serial get-state 2>&1
        ($stateOut | Out-String) | Set-Content -Path $stateFile -Encoding UTF8
        if (($stateOut -join "`n") -match "device") {
            $checks.adb_state.pass = $true
            $checks.adb_state.note = "device state is online"
        } else {
            $checks.adb_state.note = "device state not online"
        }
    } catch {
        $checks.adb_state.note = "adb get-state failed: $($_.Exception.Message)"
    }

    try {
        $model = (& adb -s $serial shell getprop ro.product.model 2>&1 | Out-String).Trim()
        $model | Set-Content -Path $modelFile -Encoding UTF8
        if ($model) {
            $checks.model.pass = $true
            $checks.model.note = $model
        } else {
            $checks.model.note = "model empty"
        }
    } catch {
        $checks.model.note = "model query failed: $($_.Exception.Message)"
    }

    try {
        $uiaOut = & adb -s $serial shell uiautomator dump /sdcard/window_dump.xml 2>&1
        ($uiaOut | Out-String) | Set-Content -Path $uiaFile -Encoding UTF8
        if (($uiaOut -join "`n") -match "UI hierarchy dumped|UI hierchary dumped") {
            $checks.uia_dump.pass = $true
            $checks.uia_dump.note = "uiautomator dump succeeded"
        } else {
            $checks.uia_dump.note = "uiautomator dump did not report success"
        }
    } catch {
        $checks.uia_dump.note = "uiautomator dump failed: $($_.Exception.Message)"
    }

    try {
        $pullOut = & adb -s $serial pull /sdcard/window_dump.xml $pullFile 2>&1
        ($pullOut | Out-String) | Set-Content -Path (Join-Path $deviceDir "uia_pull.txt") -Encoding UTF8
        if ((Test-Path $pullFile) -and ((Get-Item $pullFile).Length -gt 0)) {
            $checks.uia_pull.pass = $true
            $checks.uia_pull.note = "pulled window_dump.xml"
        } else {
            $checks.uia_pull.note = "window_dump.xml missing or empty"
        }
    } catch {
        $checks.uia_pull.note = "uia pull failed: $($_.Exception.Message)"
    }

    try {
        cmd /c "adb -s $serial exec-out screencap -p > `"$screencapFile`""
        $norm = Normalize-PngFile -Path $screencapFile
        $checks.screencap.pass = [bool]$norm.pass
        $checks.screencap.note = [string]$norm.note
    } catch {
        $checks.screencap.note = "screencap failed: $($_.Exception.Message)"
    }

    if ($SkipScrcpy) {
        $checks.scrcpy.pass = $true
        $checks.scrcpy.note = "skipped by flag"
        "scrcpy skipped" | Set-Content -Path $scrcpyFile -Encoding UTF8
    } elseif (-not $scrcpyExe) {
        $checks.scrcpy.note = "scrcpy not found in PATH"
        "scrcpy executable missing" | Set-Content -Path $scrcpyFile -Encoding UTF8
    } else {
        try {
            $proc = Start-Process -FilePath $scrcpyExe -ArgumentList @("-s", $serial, "--no-audio", "--no-control", "--window-x", "-32000", "--window-y", "-32000") -PassThru -WindowStyle Hidden
            Start-Sleep -Seconds ([Math]::Max(3, $ScrcpySmokeSeconds))
            if (-not $proc.HasExited) {
                Stop-Process -Id $proc.Id -Force
                $checks.scrcpy.pass = $true
                $checks.scrcpy.note = "scrcpy stayed alive during smoke window"
            } elseif ($proc.ExitCode -eq 0) {
                $checks.scrcpy.pass = $true
                $checks.scrcpy.note = "scrcpy started and exited cleanly"
            } else {
                $checks.scrcpy.note = "scrcpy exited early with code $($proc.ExitCode)"
            }
            "scrcpy exe: $scrcpyExe`nexit code: $($proc.ExitCode)" | Set-Content -Path $scrcpyFile -Encoding UTF8
        } catch {
            $checks.scrcpy.note = "scrcpy launch failed: $($_.Exception.Message)"
            $_ | Out-String | Set-Content -Path $scrcpyFile -Encoding UTF8
        }
    }

    return [ordered]@{
        role = $role
        serial = $serial
        checks = $checks
    }
}

$results = @()
foreach ($target in $targets) {
    $results += (Test-Target -role $target.role -serial $target.serial)
}

$overallPass = $true
foreach ($result in $results) {
    $checks = $result.checks
    foreach ($name in @("adb_connect", "adb_state", "model", "uia_dump", "uia_pull", "screencap", "scrcpy")) {
        if (-not $checks[$name].pass) {
            $overallPass = $false
        }
    }
}

$report = [ordered]@{
    schema = "quantum_rack_multidevice_signoff.v1"
    generated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    output_dir = (Resolve-Path $outDir).Path
    targets = $results
    overall_pass = $overallPass
    notes = @(
        "Use this report for G70 HU/CDE/RSE signoff when all three devices are reachable.",
        "Screencap auto-recovers PNG payload when rack output includes warning prefixes."
    )
}

$reportPath = Join-Path $outDir "rack_multidevice_report.json"
$report | ConvertTo-Json -Depth 10 | Set-Content -Path $reportPath -Encoding UTF8
Write-Host ($report | ConvertTo-Json -Depth 10)

if (-not $overallPass) {
    exit 2
}
exit 0

