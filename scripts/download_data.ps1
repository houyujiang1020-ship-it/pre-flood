[CmdletBinding()]
param([ValidateSet('sample','full')][string]$Mode = 'sample', [int]$Count = 2)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $projectRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'download_data.py') --mode $Mode --count $Count
if ($LASTEXITCODE -ne 0) { throw 'Official SpaceNet8 download failed; partial downloads are retained for resume.' }
