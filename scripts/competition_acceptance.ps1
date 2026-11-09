[CmdletBinding()]
param([int]$Port = 8765, [switch]$RunTests)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runId = 'acceptance-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$runDir = Join-Path $projectRoot "runtime\acceptance\$runId"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

& (Join-Path $PSScriptRoot 'preflight.ps1') -Port $Port -Output (Join-Path $runDir 'environment.json') | Out-Null
if ($RunTests) {
    & (Join-Path $PSScriptRoot 'run_tests.ps1') *> (Join-Path $runDir 'test-run.log')
    if ($LASTEXITCODE -ne 0) { throw 'Regression failed; acceptance package remains as failure evidence.' }
}

function Sha([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
}
function Save-Json([string]$Name, $Value) {
    $Value | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $runDir $Name) -Encoding utf8
}

$verificationPath = Join-Path $projectRoot 'data\outputs\gn-pilot-api-20260912\verification.json'
$verification = if (Test-Path -LiteralPath $verificationPath) { Get-Content -LiteralPath $verificationPath -Raw | ConvertFrom-Json } else { $null }
$readinessPath = Join-Path $projectRoot 'runtime\competition-readiness-20260912.json'
$readiness = if (Test-Path -LiteralPath $readinessPath) { Get-Content -LiteralPath $readinessPath -Raw | ConvertFrom-Json } else { $null }
$auditPath = Join-Path $projectRoot 'data\processed\full-audit-20260830\audit.json'
$reviewPath = Join-Path $projectRoot 'experiments\diagnostics\visibility\germany-20260912-v2\review_status.json'

Save-Json 'model.json' ([ordered]@{
    status = if ($verification) { 'research_verified' } else { 'blocked' }
    model = if ($verification) { $verification.model } else { $null }
    inference_verified = [bool]($verification -and $verification.inference_verified)
    accuracy_verified = [bool]($verification -and $verification.accuracy_verified)
    production_ready = [bool]($verification -and $verification.model.production_ready)
    evidence = $verificationPath
    evidence_sha256 = Sha $verificationPath
})
Save-Json 'data_manifest.json' ([ordered]@{
    source_audit = $auditPath; source_audit_sha256 = Sha $auditPath
    visibility_review = $reviewPath; visibility_review_sha256 = Sha $reviewPath
    visibility_review_complete = $false
    notes = 'SpaceNet8 structure labels are not a complete flood extent or population source.'
})
foreach ($item in @(
    @('damage_analysis.json','blocked','Complete flood extent, entity sampling, community and population evidence are missing.'),
    @('road_blockage.json','partial','Exercise closure route evidence exists; formal event road validation is missing.'),
    @('resource_dispatch.json','blocked','No verified real or organizer-approved resource ledger.'),
    @('route_analysis.json','partial','Native exercise routes passed; complete formal business acceptance is missing.'),
    @('report_manifest.json','blocked','Final disaster report awaits complete damage, population and real-resource evidence.')
)) { Save-Json $item[0] ([ordered]@{ status=$item[1]; completed=$false; run_id=$runId; notes=$item[2] }) }
$testLog = Join-Path $projectRoot 'logs\regression-20260912.log'
$testPassed = $false
if (Test-Path -LiteralPath $testLog) {
    $testText = Get-Content -LiteralPath $testLog -Raw
    $testPassed = $testText -match '9 passed in' -and $testText -match '33 passed in' -and
                  $testText -match 'Ran 13 tests' -and $testText -match 'Tests run: 53, Failures: 0'
}
Save-Json 'test_summary.json' ([ordered]@{
    run_tests_requested = [bool]$RunTests
    latest_known_log = $testLog; latest_known_log_sha256 = Sha $testLog
    latest_known_result = if ($testPassed) { 'passed' } else { 'unknown_or_failed' }
    gui_tested = $false
})
Save-Json 'evidence_manifest.json' ([ordered]@{
    run_id=$runId; created_at=(Get-Date).ToString('o'); competition_readiness=$readiness
    files=@(Get-ChildItem -LiteralPath $runDir -File | ForEach-Object { [ordered]@{name=$_.Name;sha256=Sha $_.FullName} })
    complete=$false; competition_ready=$false
})
@"
# MapGIS GUI正式验收清单 — $runId

- [ ] 官方授权MapGIS宿主启动并记录时间/环境
- [ ] FloodGuard插件加载，显示灾前、灾后和明确标记的AI Prediction
- [ ] 显示真实模型身份、SHA256、阈值和production状态
- [ ] Ground Truth Validation模式完成实体级建筑/道路相交及20项独立核验
- [ ] 完整洪水范围、面积、社区、人口和风险排序有来源证据
- [ ] 道路阻断、不可达、容量不足和多资源联合分配完成
- [ ] NetCls救援路线避开阻断边，JNI前置门禁全部通过
- [ ] 专题图与完整报告生成并登记截图/JSON/日志

当前包由自动阶段生成，未勾选项不得改写为通过。
"@ | Set-Content -LiteralPath (Join-Path $runDir 'GUI_CHECKLIST.md') -Encoding utf8
Save-Json 'evidence_manifest.json' ([ordered]@{
    run_id=$runId; created_at=(Get-Date).ToString('o'); competition_readiness=$readiness
    files=@(Get-ChildItem -LiteralPath $runDir -File | Where-Object Name -ne 'evidence_manifest.json' |
        ForEach-Object { [ordered]@{name=$_.Name;sha256=Sha $_.FullName} })
    complete=$false; competition_ready=$false
})
Write-Output (@{run_id=$runId;directory=$runDir;automatic_complete=$true;competition_ready=$false} | ConvertTo-Json)
