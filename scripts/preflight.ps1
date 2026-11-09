[CmdletBinding()]
param([int]$Port = 8765, [string]$Output = '')

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if (-not $Output) { $Output = Join-Path $projectRoot "runtime\preflight-$timestamp.json" }
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$trainingPython = Join-Path $projectRoot '.venv-training\Scripts\python.exe'
$mapgisProgram = 'C:\Program Files\MapGIS 10\Program'

function File-State([string]$Path) {
    [ordered]@{ path = $Path; exists = Test-Path -LiteralPath $Path -PathType Leaf }
}

$licenseProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'MapGIS|DesktopLauncher|MapGISEngine' } |
    Select-Object ProcessId, Name, CommandLine)
$portOwner = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess)
$health = $null
try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3 } catch {}
$modelInfo = $null
try { $modelInfo = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/model/info" -TimeoutSec 3 } catch {}
$cuda = [ordered]@{ available = $false; device = $null; error = $null }
if (Test-Path -LiteralPath $trainingPython) {
    $cudaResult = & $trainingPython -c "import json,torch; print(json.dumps({'available':torch.cuda.is_available(),'device':torch.cuda.get_device_name() if torch.cuda.is_available() else None}))" 2>&1
    if ($LASTEXITCODE -eq 0) { $cuda = $cudaResult | ConvertFrom-Json } else { $cuda.error = "$cudaResult" }
} else { $cuda.error = 'Training Python is missing' }

$realLedger = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'data') -Filter '*.json' -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'resource|ledger' } |
    ForEach-Object {
        try {
            $value = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
            if ($value.resource_mode -eq 'real' -or $value.is_exercise -eq $false) { $_.FullName }
        } catch {}
    }
$report = [ordered]@{
    schema_version = 1
    run_id = "preflight-$timestamp"
    checked_at = (Get-Date).ToString('o')
    mapgis = [ordered]@{ program = $mapgisProgram; installed = Test-Path -LiteralPath $mapgisProgram }
    license_host = [ordered]@{ running = $licenseProcesses.Count -gt 0; processes = $licenseProcesses }
    java = [ordered]@{
        project_jdk17 = File-State (Join-Path $projectRoot 'tools\jdk-17\jdk-17.0.20.1+1\bin\java.exe')
        mapgis_java21 = File-State (Join-Path $mapgisProgram 'java\jre21\bin\desktopjava.exe')
    }
    python = [ordered]@{ inference = File-State $python; training = File-State $trainingPython }
    ai_service = [ordered]@{ reachable = $null -ne $health; health = $health; model = $modelInfo }
    cuda = $cuda
    model = [ordered]@{
        production_directory = File-State (Join-Path $projectRoot 'models\production\model.json')
        latest_research_verification = File-State (Join-Path $projectRoot 'data\outputs\gn-pilot-api-20260912\verification.json')
        production_ready = [bool]($modelInfo -and $modelInfo.production_ready -eq $true)
    }
    dataset = [ordered]@{
        source_root_exists = Test-Path -LiteralPath (Join-Path $projectRoot '11')
        full_audit = File-State (Join-Path $projectRoot 'data\processed\full-audit-20260830\audit.json')
        visibility_review = File-State (Join-Path $projectRoot 'experiments\diagnostics\visibility\germany-20260912-v2\review_status.json')
    }
    resource_ledger = [ordered]@{ real_candidates = @($realLedger); verified_real_available = @($realLedger).Count -gt 0 }
    ports = [ordered]@{ requested = $Port; listeners = $portOwner }
    ready_for_competition_demo = $false
    notes = 'Environment inventory only. MapGIS process discovery is not license or GUI acceptance; production and real-ledger gates remain evidence-driven.'
}
$target = [IO.Path]::GetFullPath($Output)
New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $target -Encoding utf8
Write-Output ($report | ConvertTo-Json -Depth 5)
Write-Output "Preflight evidence: $target"

