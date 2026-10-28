# Windows 11 / PowerShell setup. Installs pinned dependencies; never downloads model weights by itself.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1            # core app
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -WithML    # + sentence-transformers / faster-whisper
param([switch]$WithML)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r backend\requirements-dev.txt
if ($WithML) { .\.venv\Scripts\pip.exe install -r backend\requirements-ml.txt }
Push-Location frontend; npm ci; npm run build; Pop-Location
.\.venv\Scripts\python.exe scripts\check_setup.py
Write-Host "Next: scripts\dev.ps1   (models later: python scripts\download_models.py --all)"
