[CmdletBinding()]
param(
    [string]$HostAddress = '127.0.0.1',
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$serviceRoot = Join-Path $projectRoot 'app\ai-service'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python virtual environment is missing. Run scripts\setup_python.ps1 first.'
}
Set-Location -LiteralPath $serviceRoot
& $python -m uvicorn app.main:app --host $HostAddress --port $Port
