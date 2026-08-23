[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    winget install --id Python.Python.3.10 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
}
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python 3.10 installation did not produce the expected executable.'
}

$venv = Join-Path $projectRoot '.venv'
if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts\python.exe'))) {
    & $python -m venv $venv
}
& (Join-Path $venv 'Scripts\python.exe') --version
