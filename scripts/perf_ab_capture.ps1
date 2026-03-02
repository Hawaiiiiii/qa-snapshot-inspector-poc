param(
    [ValidateSet("local", "rdp", "both")]
    [string]$Env = "both",
    [int]$Runs = 3,
    [string]$Session = "",
    [ValidateSet("balanced", "strict")]
    [string]$Targets = "balanced",
    [int]$Rounds = 100,
    [switch]$RequireAllPass = $false,
    [switch]$SkipEnforceTargets = $false
)

$ErrorActionPreference = 'Stop'

$python = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
$python = [System.IO.Path]::GetFullPath($python)
if (-not (Test-Path $python)) {
    throw "Python interpreter not found at $python"
}

function Run-PerfCapture([string]$EnvName) {
    $args = @(
        "scripts\\perf_ab_capture.py",
        "--env", $EnvName,
        "--runs", $Runs,
        "--targets", $Targets,
        "--rounds", $Rounds
    )
    if ($Session) {
        $args += @("--session", $Session)
    }
    if (-not $SkipEnforceTargets) {
        $args += "--enforce-targets"
    }
    if ($RequireAllPass) {
        $args += "--require-all-pass"
    }
    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw "perf_ab_capture failed for environment '$EnvName'"
    }
}

if ($Env -eq "both") {
    Run-PerfCapture -EnvName "local"
    Run-PerfCapture -EnvName "rdp"
} else {
    Run-PerfCapture -EnvName $Env
}

Write-Host "[perf-ab] capture complete"
