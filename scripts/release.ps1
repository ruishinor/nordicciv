# Build the consolidated release package after all gates pass.  .\scripts\release.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$venvPy = '.venv\Scripts\python.exe'
$python = if (Test-Path $venvPy) { (Resolve-Path $venvPy).Path } else { (Get-Command python -ErrorAction Stop).Source }
$version = (Get-Content VERSION -Raw).Trim()
& $python -m pipeline release
if ($LASTEXITCODE -ne 0) { Write-Host "Release FAILED: no package was produced." -ForegroundColor Red; exit 1 }
$zip = "dist\nordicciv-$version.zip"
if (-not (Test-Path $zip)) { Write-Host "Release reported success but $zip is missing." -ForegroundColor Red; exit 1 }
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
Write-Host "Package: $((Resolve-Path $zip).Path)" -ForegroundColor Green
Write-Host "SHA-256: $hash"
