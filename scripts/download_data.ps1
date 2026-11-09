[CmdletBinding()]
param(
    [ValidateSet('sample','full')][string]$Mode = 'sample',
    [int]$Count = 2,
    [ValidateRange(1,16)][int]$Workers = 8,
    [ValidateSet('Germany_Training_Public','Louisiana-East_Training_Public')]
    [string[]]$Area
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @('--mode', $Mode, '--count', $Count, '--workers', $Workers)
foreach ($selectedArea in $Area) { $arguments += @('--area', $selectedArea) }
& (Join-Path $projectRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'download_data.py') @arguments
if ($LASTEXITCODE -ne 0) { throw 'Official SpaceNet8 download failed; partial downloads are retained for resume.' }
