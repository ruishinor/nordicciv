# Serve the app locally (the built data are included; no download needed).  .\scripts\serve.ps1 [-Port 8765]
[CmdletBinding()]
param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$venvPy = '.venv\Scripts\python.exe'
$python = if (Test-Path $venvPy) { (Resolve-Path $venvPy).Path } else { (Get-Command python -ErrorAction Stop).Source }
if (-not (Test-Path 'web\data\cities.json')) { throw "web\data is missing: this is not a complete NordicCiv folder" }
Write-Host "Open http://127.0.0.1:$Port in a browser (Ctrl+C to stop)" -ForegroundColor Green
& $python -m pipeline serve --port $Port
