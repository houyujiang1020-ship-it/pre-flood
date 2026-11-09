param(
    [ValidateSet('Audit', 'Train')][string]$Mode = 'Audit',
    [string]$Config = 'config/training.class-aware-crop-pilot-20261005.json',
    [string]$RunId = (Get-Date -Format 'yyyyMMdd-HHmmss'),
    [switch]$MineFullTrain
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv-training/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Training Python missing: $python" }
$run = Join-Path $root "experiments/accuracy-pipeline-$RunId"
if (Test-Path -LiteralPath $run) { throw "Run directory already exists: $run" }
New-Item -ItemType Directory -Path $run | Out-Null
Push-Location $root
try {
    $audit = 'experiments/accuracy-pipeline-20261005/split_audit.json'
    if (-not (Test-Path -LiteralPath $audit)) {
        & $python scripts/audit_accuracy_split.py
        if ($LASTEXITCODE -ne 0) { throw 'Split audit failed' }
    }
    $auditValue = Get-Content $audit -Raw | ConvertFrom-Json
    if ($auditValue.duplicate_sample_ids -ne 0 -or $auditValue.cross_split_reused_pre_images.Count -ne 0 -or
        $auditValue.cross_split_positive_bbox_overlaps.Count -ne 0) { throw 'Split audit failed' }
    $baselineConfig = 'config/training.foundation-initialized-four-class-20260926.json'
    $baselineCheckpoint = 'models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth'
    & $python scripts/evaluate_accuracy_candidate.py --config $baselineConfig --checkpoint $baselineCheckpoint --output "$run/baseline_metrics.json"
    if ($LASTEXITCODE -ne 0) { throw 'Baseline evaluation failed' }
    if ($Mode -eq 'Train') {
        $configPath = Resolve-Path -LiteralPath $Config
        $candidateConfig = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        $candidateOutput = Join-Path $root $candidateConfig.output_dir
        if (Test-Path -LiteralPath (Join-Path $candidateOutput 'last_model.pth')) {
            throw "Candidate run already exists; choose a fresh model_id/output_dir: $candidateOutput"
        }
        & $python app/training/train_full.py --config $configPath
        if ($LASTEXITCODE -ne 0) { throw 'Candidate training failed' }
        $checkpoint = Join-Path $candidateOutput 'best_model.pth'
        & $python scripts/evaluate_accuracy_candidate.py --config $configPath --checkpoint $checkpoint --output "$run/candidate_metrics.json"
        if ($LASTEXITCODE -ne 0) { throw 'Candidate evaluation failed' }
        & $python scripts/model_promotion.py --baseline "$run/baseline_metrics.json" --candidate "$run/candidate_metrics.json" --output "$run/promotion.json"
        if ($LASTEXITCODE -ne 0) { throw 'Promotion gate failed' }
        & $python scripts/search_development_thresholds.py --config $configPath --checkpoint $checkpoint --output "$run/thresholds"
        if ($LASTEXITCODE -ne 0) { throw 'Threshold diagnostic failed' }
    }
    if ($MineFullTrain) {
        & $python tools/mine_failure_cases.py --config $baselineConfig --checkpoint $baselineCheckpoint --split train --output "$run/train_mining"
        if ($LASTEXITCODE -ne 0) { throw 'Train-only error mining failed' }
    }
    Write-Host "Accuracy pipeline complete: $run"
    Write-Host 'All validation results are development-only; independent test remains pending.'
} finally {
    Pop-Location
}
