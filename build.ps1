$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.22.3
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name GHubIndicator app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Host 'Built dist\GHubIndicator.exe'
