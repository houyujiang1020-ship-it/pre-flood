[CmdletBinding()]
param([string]$MapGisProgram = 'C:\Program Files\MapGIS 10\Program', [int]$Port = 8765, [switch]$AiOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @('start', '--program', $MapGisProgram, '--port', $Port)
if ($AiOnly) { $arguments += '--ai-only' }
& (Join-Path $projectRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'demo_manager.py') @arguments
if ($LASTEXITCODE -ne 0) { throw 'Demo startup failed; owned processes were cleaned up. Inspect logs and BLOCKERS.md.' }
