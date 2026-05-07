$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

.\.venv\Scripts\python.exe ai_watchkeeper.py
