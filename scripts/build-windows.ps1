$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Run from the repository root in Windows PowerShell 5.1+ or PowerShell 7.
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher 'py' was not found. Install Python 3.11+ from python.org and enable the launcher."
}

py -3.11 -m venv .venv
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Could not create the Python 3.11 virtual environment."
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -e ".[test,build]"
& $Python -m pytest
if ($LASTEXITCODE -ne 0) {
    throw "Tests failed; Windows packaging has been stopped."
}

& $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name NovelTrad --paths src --collect-all uvicorn --collect-all fitz --add-data "data;data" scripts/noveltrad_launcher.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed to package NovelTrad."
}

Write-Host ""
Write-Host "Build complete: $Root\dist\NovelTrad\NovelTrad.exe"
Write-Host "Distribute the entire dist\NovelTrad folder, not only the EXE."
Write-Host "User library remains in %LOCALAPPDATA%\NovelTrad and is not bundled."
