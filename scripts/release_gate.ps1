param(
    [switch]$BuildExe = $false,
    [switch]$Strict = $false,
    [switch]$RequirePython311 = $false,
    [switch]$RequirePackagingBaseline311 = $false
)

$ErrorActionPreference = 'Stop'

$python = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
$python = [System.IO.Path]::GetFullPath($python)

if (-not (Test-Path $python)) {
    throw "Python interpreter not found at $python"
}

Write-Host "[gate] Python: $python"
& $python --version

$pyVersion = (& $python -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')").Trim()
$versionParts = $pyVersion.Split('.')
$pyMajor = [int]$versionParts[0]
$pyMinor = [int]$versionParts[1]

if (($pyMajor -lt 3) -or (($pyMajor -eq 3) -and ($pyMinor -lt 11))) {
    throw "Python >=3.11 is required for this gate; found $pyVersion"
}

$enforcePackagingBaseline311 = $RequirePython311 -or $RequirePackagingBaseline311
if ($RequirePython311 -and -not $RequirePackagingBaseline311) {
    Write-Warning "-RequirePython311 is deprecated; use -RequirePackagingBaseline311."
}
if ($enforcePackagingBaseline311 -and -not (($pyMajor -eq 3) -and ($pyMinor -eq 11))) {
    throw "Python 3.11.x packaging baseline is required for this gate; found $pyVersion"
}

if (($pyMajor -gt 3) -or (($pyMajor -eq 3) -and ($pyMinor -gt 14))) {
    Write-Warning "Python $pyVersion is newer than validated 2.0 set (3.11 and 3.14)."
}

Write-Host "[gate] pytest"
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

Write-Host "[gate] compileall"
& $python -m compileall src\qa_snapshot_tool src\qa_snapshot_native scripts
if ($LASTEXITCODE -ne 0) { throw "compileall failed" }

if ($Strict) {
    Write-Host "[gate] hotspot acceptance (balanced)"
    & $python scripts\profile_hotspots.py --targets balanced --enforce-targets
    if ($LASTEXITCODE -ne 0) {
        throw "hotspot acceptance failed (use a recorded session with frame+xml artifacts)"
    }
}

if ($BuildExe) {
    Write-Host "[gate] pyinstaller build"
    & $python -m PyInstaller QuantumInspector.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }
    if (-not (Test-Path dist\QuantumInspector.exe)) {
        throw "dist\\QuantumInspector.exe missing"
    }
}

Write-Host "[gate] PASS"
