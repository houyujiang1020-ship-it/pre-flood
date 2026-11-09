[CmdletBinding()]
param([string]$MapGisProgram = 'C:\Program Files\MapGIS 10\Program', [int]$Port = 8765,
      [ValidateSet('e4-research','siamunet-smoke')][string]$Model = 'e4-research', [switch]$AiOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @('start', '--program', $MapGisProgram, '--port', $Port, '--model', $Model)
if ($AiOnly) { $arguments += '--ai-only' }
& (Join-Path $projectRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'demo_manager.py') @arguments
if ($LASTEXITCODE -ne 0) { throw 'Demo startup failed. Existing sessions may still be running; inspect the error above and runtime/demo-state.json. Save and close MapGIS before running stop_demo.ps1.' }
