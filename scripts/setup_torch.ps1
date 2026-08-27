[CmdletBinding()]
param([ValidateSet('Training', 'Inference')][string]$Environment = 'Training')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$basePython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $basePython)) { throw 'Run setup_python.ps1 first.' }
$python = $basePython
if ($Environment -eq 'Training') {
    $trainingEnv = Join-Path $projectRoot '.venv-training'
    $python = Join-Path $trainingEnv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        & $basePython -m venv $trainingEnv
        if ($LASTEXITCODE -ne 0) { throw 'Unable to create training environment.' }
    }
}
$wheelDir = Join-Path $projectRoot 'tools\wheels'
New-Item -ItemType Directory -Path $wheelDir -Force | Out-Null
$wheel = Join-Path $wheelDir 'torch-2.5.1+cu121-cp310-cp310-win_amd64.whl'
$expectedHash = '9b22d6d98aa56f9317902dec0e066814a6edba1aada90110ceea2bb0678df22f'
# Hash published by the official PyTorch cu121 wheel index, verified 2026-08-27.
if (-not (Test-Path -LiteralPath $wheel) -or (Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash -ne $expectedHash) {
    $partial = "$wheel.part"
    $free = (Get-PSDrive -Name ([IO.Path]::GetPathRoot($projectRoot).TrimEnd('\').TrimEnd(':'))).Free
    if ($free -lt 8GB) { throw 'At least 8 GB free is required for wheel download and unpacking.' }
    & curl.exe --fail --location --retry 3 --continue-at - --output $partial 'https://download.pytorch.org/whl/cu121/torch-2.5.1%2Bcu121-cp310-cp310-win_amd64.whl'
    if ($LASTEXITCODE -ne 0) { throw 'PyTorch download failed; partial retained for resume.' }
    if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $expectedHash) { throw 'PyTorch SHA256 mismatch; refusing installation.' }
    Move-Item -LiteralPath $partial -Destination $wheel -Force
}
$requirements = if ($Environment -eq 'Training') { 'app\training\requirements-lock.txt' } else { 'app\ai-service\requirements-torch.txt' }
& $python -m pip install --find-links $wheelDir -r (Join-Path $projectRoot $requirements)
if ($LASTEXITCODE -ne 0) { throw 'PyTorch environment installation failed.' }
& $python -c "import torch; print(torch.__version__); print('CUDA available:', torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw 'PyTorch import verification failed.' }
