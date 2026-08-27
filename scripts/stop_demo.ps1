[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $projectRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'demo_manager.py') stop
if ($LASTEXITCODE -ne 0) { throw 'Safe shutdown refused or failed. Inspect runtime/demo-state.json; do not kill unrelated processes.' }
