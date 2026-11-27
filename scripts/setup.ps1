# NordicCiv: create a virtual environment and install dependencies (Windows PowerShell 5.1 or PowerShell 7).
#   .\scripts\setup.ps1            # development (compatible versions)
#   .\scripts\setup.ps1 -Locked    # the exact versions the release data were built with
#   .\scripts\setup.ps1 -Browser   # also install Playwright's Chromium and axe-core for the browser tests
[CmdletBinding()]
param([switch]$Locked, [switch]$Browser)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python 3.11+ was not found on PATH. Install it from https://www.python.org/downloads/ and try again." }

if (-not (Test-Path .venv)) { & $py.Source -m venv .venv; if ($LASTEXITCODE -ne 0) { throw "Could not create .venv" } }
$venvPy = Join-Path (Resolve-Path .venv) 'Scripts\python.exe'
if (-not (Test-Path $venvPy)) { throw "Virtual environment is incomplete: $venvPy not found" }

& $venvPy -m pip install --upgrade pip | Out-Null
$req = if ($Locked) { 'requirements-lock.txt' } else { 'requirements.txt' }
& $venvPy -m pip install -r $req
if ($LASTEXITCODE -ne 0) { throw "pip install -r $req failed" }

if ($Browser) {
  & $venvPy -m playwright install chromium
  if ($LASTEXITCODE -ne 0) { throw "playwright install chromium failed" }
  $npm = Get-Command npm -ErrorAction SilentlyContinue
  if ($npm) {
    & $npm.Source install --prefix tests/.node axe-core@4 --silent
    if ($LASTEXITCODE -ne 0) { Write-Warning "axe-core could not be installed; the accessibility journey will be reported as SKIP" }
  } else { Write-Warning "npm not found: the accessibility journey will be reported as SKIP" }
}
Write-Host "Ready. Activate with: .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
