# Validation gates.  .\scripts\validate.ps1 [-Mode built|source|release] [-Browser]
#   built   : the shipped web/data files on their own (works on any copy)
#   source  : also reconciles with the original downloads in data\raw (needs the raw data)
#   release : source + unit and browser evidence for this exact candidate (app, data, tests) + accepted key totals
# -Browser runs the 21 browser journeys (0–20) first (starts and stops a local server).
[CmdletBinding()]
param([ValidateSet('built', 'source', 'release')][string]$Mode = 'built', [switch]$Browser, [int]$Port = 8765, [string]$Python = "")
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$venvPy = '.venv\Scripts\python.exe'
$env:PYTHONUTF8 = "1"
$python = if ($Python) { $Python } elseif (Test-Path $venvPy) { (Resolve-Path $venvPy).Path } else { (Get-Command python -ErrorAction Stop).Source }
$failed = $false

Write-Host "== unit tests" -ForegroundColor Cyan
& $python tests\run_unit.py
if ($LASTEXITCODE -ne 0) { $failed = $true }

if ($Browser -or $Mode -eq 'release') {
  Write-Host "== browser journeys" -ForegroundColor Cyan
  $server = Start-Process -FilePath $python -ArgumentList '-m', 'pipeline', 'serve', '--port', $Port -PassThru -WindowStyle Hidden
  try {
    Start-Sleep -Seconds 2
    & $python tests\smoke_browser.py "http://127.0.0.1:$Port/"
    if ($LASTEXITCODE -ne 0) { $failed = $true }
  } finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
  }
}

Write-Host "== data validation ($Mode)" -ForegroundColor Cyan
& $python -m pipeline check --mode $Mode
if ($LASTEXITCODE -ne 0) { $failed = $true }

if ($failed) { Write-Host "VALIDATION FAILED" -ForegroundColor Red; exit 1 }
Write-Host "All requested gates passed (mode: $Mode)." -ForegroundColor Green
