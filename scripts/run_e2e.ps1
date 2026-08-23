[CmdletBinding()]
param([int]$Port = 8765)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$serviceRoot = Join-Path $projectRoot 'app\ai-service'
$demoRoot = Join-Path $projectRoot 'data\demo'
$outputRoot = Join-Path $projectRoot 'data\outputs\e2e'

& $python (Join-Path $PSScriptRoot 'create_demo_data.py') | Out-Host
$process = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $serviceRoot -WindowStyle Hidden -PassThru
try {
    $healthy = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 1
            if ($health.status -eq 'ok') { $healthy = $true; break }
        } catch { Start-Sleep -Milliseconds 250 }
    }
    if (-not $healthy) { throw 'AI service did not become healthy.' }

    & (Join-Path $projectRoot 'scripts\setup_java.ps1') | Out-Host
    Push-Location -LiteralPath (Join-Path $projectRoot 'app\mapgis-flood-desktop')
    try {
        mvn '-Dtest=RealAiServiceIT' "-Dai.url=http://127.0.0.1:$Port" "-Ddemo.pre=$(Join-Path $demoRoot '灾前演示.png')" "-Ddemo.post=$(Join-Path $demoRoot '灾后演示.png')" "-Ddemo.output=$outputRoot" test
        if ($LASTEXITCODE -ne 0) { throw "E2E test failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
} finally {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id }
}
