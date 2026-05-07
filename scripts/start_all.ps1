$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $root -WindowStyle Hidden
Start-Sleep -Seconds 2
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList @("ai_watchkeeper.py") -WorkingDirectory $root -WindowStyle Hidden
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList @("demo_sensors.py") -WorkingDirectory $root -WindowStyle Hidden

Write-Host "Started backend, AI watchkeeper, and demo sensors."
Write-Host "Open http://127.0.0.1:8000/ui/"
