[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& (Join-Path $projectRoot '.venv-training\Scripts\python.exe') -m tools.visibility_review.cli report
if ($LASTEXITCODE -ne 0) { throw 'Review report failed.' }
Write-Host (Join-Path $projectRoot 'docs\VISIBILITY_REVIEW_REPORT.md')
