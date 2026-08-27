[CmdletBinding()]
param([string]$Config = '', [switch]$Resume, [int]$Epochs = 0)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Config) { $Config = Join-Path $projectRoot 'config\training.example.json' }
$arguments = @('--config', $Config)
if ($Resume) { $arguments += '--resume' }
if ($Epochs -gt 0) { $arguments += @('--epochs', $Epochs) }
& (Join-Path $projectRoot '.venv-training\Scripts\python.exe') (Join-Path $projectRoot 'app\training\train_full.py') @arguments
if ($LASTEXITCODE -ne 0) { throw 'Configured training failed; inspect the error before using a checkpoint.' }
