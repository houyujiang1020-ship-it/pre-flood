[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python virtual environment is missing. Run scripts\setup_python.ps1 first.'
}
Push-Location -LiteralPath (Join-Path $projectRoot 'app\ai-service')
try {
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "AI tests failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

& (Join-Path $projectRoot 'scripts\setup_java.ps1') | Out-Host
Push-Location -LiteralPath (Join-Path $projectRoot 'app\mapgis-flood-desktop')
try {
    mvn test
    if ($LASTEXITCODE -ne 0) { throw "Java tests failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}
