[CmdletBinding()]
param([int]$E2EPort = 18765)

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

$trainingPython = Join-Path $projectRoot '.venv-training\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $trainingPython)) {
    throw 'Training environment missing; training regression cannot be claimed complete.'
}
& $trainingPython -m pytest (Join-Path $projectRoot 'tests') -q
if ($LASTEXITCODE -ne 0) { throw 'Repository script tests failed.' }

& $trainingPython -m unittest discover -s (Join-Path $projectRoot 'app\training') -p 'test_*.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Training pipeline tests failed.' }

& (Join-Path $projectRoot 'scripts\setup_java.ps1') | Out-Host
Push-Location -LiteralPath (Join-Path $projectRoot 'app\mapgis-flood-desktop')
try {
    # Keep Java 17 core tests separate from the Java 21 installed-SDK build.
    mvn '-Dfloodguard.build.directory=target-core-tests' test
    if ($LASTEXITCODE -ne 0) { throw "Java tests failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

& (Join-Path $projectRoot 'scripts\run_e2e.ps1') -Port $E2EPort | Out-Host
& (Join-Path $projectRoot 'scripts\build_mapgis_plugin.ps1') | Out-Host
