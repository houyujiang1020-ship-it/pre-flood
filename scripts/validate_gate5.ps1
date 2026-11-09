param([Parameter(Mandatory=$true)][string]$RunDirectory)
$Python = Join-Path $PSScriptRoot '..\.venv-training\Scripts\python.exe'
& $Python (Join-Path $PSScriptRoot 'validate_gate5.py') $RunDirectory
exit $LASTEXITCODE
