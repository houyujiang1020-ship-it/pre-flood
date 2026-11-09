[CmdletBinding()]
param([string]$StorePath = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $StorePath) { $StorePath = Join-Path $projectRoot 'experiments\diagnostics\visibility\germany-20260912-v2' }
$pidFile = Join-Path ([IO.Path]::GetFullPath($StorePath)) 'service_process.json'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No owned review service recorded.'; return }
$state = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
$owned = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
if (-not $owned) { Write-Host 'Review service is already stopped.'; return }
$info = Get-CimInstance Win32_Process -Filter "ProcessId=$($state.pid)"
if ($owned.StartTime.ToUniversalTime().Ticks.ToString() -ne $state.start_ticks -or $owned.Path -ne $state.python -or $info.CommandLine -notlike '*tools.visibility_review.cli*serve*' -or $info.CommandLine -notlike "*$($state.instance)*") {
    throw 'Process identity mismatch; refusing to stop an unrelated process.'
}
$bootstrap = Invoke-RestMethod -Uri "$($state.url)/api/bootstrap" -TimeoutSec 5
Invoke-RestMethod -Method Post -Uri "$($state.url)/api/shutdown" -Headers @{'X-Review-Token'=$bootstrap.token} -TimeoutSec 5 | Out-Null
# Graceful shutdown lets in-flight writes finish; never force-kill during a journal append.
Wait-Process -Id $owned.Id -Timeout 15 -ErrorAction Stop
Write-Host "Stopped owned visibility review PID=$($state.pid). Reviews are already durable."
