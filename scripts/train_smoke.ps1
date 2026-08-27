[CmdletBinding()]
param([int]$Epochs = 2, [int]$ImageSize = 128)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $projectRoot '.venv-training\Scripts\python.exe') (Join-Path $projectRoot 'app\training\train_smoke.py') --epochs $Epochs --size $ImageSize
if ($LASTEXITCODE -ne 0) { throw 'Smoke training failed; inspect the error before using any checkpoint.' }
