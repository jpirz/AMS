$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

.\.venv\Scripts\python.exe demo_sensors.py
