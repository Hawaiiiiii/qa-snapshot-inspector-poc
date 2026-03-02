param(
    [switch]$BuildExe = $false,
    [switch]$Strict = $false
)

$ErrorActionPreference = 'Stop'

$python = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
$python = [System.IO.Path]::GetFullPath($python)

if (-not (Test-Path $python)) {
    throw "Python interpreter not found at $python"
}

Write-Host "[gate] Python: $python"
& $python --version

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
