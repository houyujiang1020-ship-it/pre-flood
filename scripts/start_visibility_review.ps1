[CmdletBinding()]
param([int]$Port = 18766, [switch]$OpenBrowser, [string]$StorePath = '', [switch]$SkipWarm)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonExe = Join-Path $projectRoot '.venv-training\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Missing .venv-training Python. See tools/visibility_review/README.md.' }
if (-not $StorePath) { $StorePath = Join-Path $projectRoot 'experiments\diagnostics\visibility\germany-20260912-v2' }
$StorePath = [IO.Path]::GetFullPath($StorePath)
New-Item -ItemType Directory -Path $StorePath -Force | Out-Null
$startLock = [IO.File]::Open((Join-Path $StorePath '.startup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
try {
    $pidFile = Join-Path $StorePath 'service_process.json'
    $readyPath = Join-Path $StorePath 'service_ready.json'
    $basePython = (& $pythonExe -c "import sys; print(sys._base_executable)").Trim()
    if (Test-Path -LiteralPath $pidFile) {
        $old = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
        $existing = Get-Process -Id $old.pid -ErrorAction SilentlyContinue
        if ($existing -and $existing.StartTime.ToUniversalTime().Ticks.ToString() -eq $old.start_ticks) {
            Write-Host "Review service already running: $($old.url) PID=$($old.pid)"
            if ($OpenBrowser) { Start-Process $old.url }
            return
        }
    }
    # Windows venv python.exe redirects to a child base interpreter. Recover only
    # a ready PID whose binary, module, store and random instance all match.
    if (Test-Path -LiteralPath $readyPath) {
        $oldReady = Get-Content -LiteralPath $readyPath -Raw | ConvertFrom-Json
        $running = Get-Process -Id $oldReady.pid -ErrorAction SilentlyContinue
        $runningInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$($oldReady.pid)"
        if ($running -and $oldReady.store -eq $StorePath -and $running.Path -in @($pythonExe, $basePython) -and $runningInfo.CommandLine.Contains($oldReady.instance) -and $runningInfo.CommandLine.Contains($StorePath) -and $runningInfo.CommandLine -like '*tools.visibility_review.cli*serve*') {
            @{pid=$running.Id; start_ticks=$running.StartTime.ToUniversalTime().Ticks.ToString(); instance=$oldReady.instance; url=$oldReady.url; store=$StorePath; python=$running.Path} | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding utf8
            Write-Host "Review service already running: $($oldReady.url) PID=$($running.Id)"
            if ($OpenBrowser) { Start-Process $oldReady.url }
            return
        }
    }
    & $pythonExe -c "import sys,fastapi,uvicorn,rasterio,PIL; assert sys.version_info[:2] == (3,10); print('Python 3.10 review dependencies OK')"
    if ($LASTEXITCODE -ne 0) { throw 'Review dependencies missing; see README.' }
    & $pythonExe -m tools.visibility_review.cli check --store $StorePath
    if ($LASTEXITCODE -ne 0) { throw 'Manifest preflight failed; inspect review_integrity_report.json.' }
    if (-not $SkipWarm) {
        Write-Host 'Checking/building display-only preview cache (first run may take several minutes)...'
        & $pythonExe -m tools.visibility_review.cli warm --store $StorePath
        if ($LASTEXITCODE -ne 0) { throw 'Preview preflight failed.' }
    }
    $instance = [guid]::NewGuid().ToString('N')
    $outLog = Join-Path $projectRoot "logs\visibility-review-$instance.stdout.log"
    $errLog = Join-Path $projectRoot "logs\visibility-review-$instance.stderr.log"
    $arguments = @('-m', 'tools.visibility_review.cli', 'serve', '--port', $Port, '--store', ('"' + $StorePath + '"'), '--instance', $instance)
    $child = Start-Process -FilePath $pythonExe -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    $startTicks = $child.StartTime.ToUniversalTime().Ticks.ToString()
    $ready = $null
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        $child.Refresh()
        if ($child.HasExited) { throw "Review service exited. Read $errLog" }
        if (Test-Path -LiteralPath $readyPath) {
            $candidate = Get-Content -LiteralPath $readyPath -Raw | ConvertFrom-Json
            $actual = Get-Process -Id $candidate.pid -ErrorAction SilentlyContinue
            $actualInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$($candidate.pid)"
            if ($candidate.instance -eq $instance -and $actual -and ($candidate.pid -eq $child.Id -or $actualInfo.ParentProcessId -eq $child.Id) -and $actual.Path -in @($pythonExe, $basePython)) {
                try {
                    $health = Invoke-RestMethod -Uri "$($candidate.url)/health" -TimeoutSec 2
                    if ($health.service -eq 'germany-visibility-review' -and $health.store -eq $StorePath) { $ready = $candidate; break }
                } catch { }
            }
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw "Service not ready. Own PID=$($child.Id), inspect $errLog" }
    @{pid=$actual.Id; start_ticks=$actual.StartTime.ToUniversalTime().Ticks.ToString(); instance=$instance; url=$ready.url; store=$StorePath; python=$actual.Path} | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding utf8
    Write-Host "Germany Visibility Review: $($ready.url) PID=$($actual.Id)"
    Write-Host "Log: $(Join-Path $projectRoot 'logs\visibility-review.log')"
    if ($OpenBrowser) { Start-Process $ready.url }
} finally { $startLock.Dispose() }
