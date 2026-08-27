[CmdletBinding()]
param([int]$Port = 18767)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$sample = Join-Path $projectRoot 'models\checkpoints\spacenet8-smoke'
& (Join-Path $PSScriptRoot 'start_demo.ps1') -AiOnly -Port $Port
try {
    & (Join-Path $PSScriptRoot 'setup_java.ps1') | Out-Host
    Push-Location -LiteralPath (Join-Path $projectRoot 'app\mapgis-flood-desktop')
    try {
        mvn '-Dtest=RealAiServiceIT' "-Dai.url=http://127.0.0.1:$Port" '-Dai.expectedBackend=siamunet-smoke' '-Dai.expectedDevice=cuda' `
            "-Ddemo.pre=$(Join-Path $sample 'validation_pre.png')" "-Ddemo.post=$(Join-Path $sample 'validation_post.png')" `
            "-Ddemo.output=$(Join-Path $projectRoot 'data\outputs\model-http')" test
        if ($LASTEXITCODE -ne 0) { throw 'Real GPU model HTTP integration failed.' }
    } finally { Pop-Location }
} finally { & (Join-Path $PSScriptRoot 'stop_demo.ps1') }
