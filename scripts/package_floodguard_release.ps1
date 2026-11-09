[CmdletBinding()]
param([string]$Destination)

$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $Destination) { $Destination = Join-Path $repository 'FloodGuard-Release' }
$destinationFull = [System.IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $destinationFull) { throw "发布目录已存在，避免混入旧文件：$destinationFull" }
$jar = Join-Path $repository 'app\mapgis-flood-desktop\target\mapgis-floodguard-plugin.jar'
if (-not (Test-Path -LiteralPath $jar)) { throw "请先构建插件：$jar" }
$dataset = Join-Path $repository 'DemoDataset_Final'
foreach ($name in @('01_flood_prediction.json','02_buildings.geojson','03_roads.geojson',
        '04_population.csv','05_resources.json','06_scenario.json','07_flood_extent.geojson',
        '08_population_grid.geojson','09_admin_area.geojson','pre.tif','post.tif','README.md')) {
    if (-not (Test-Path -LiteralPath (Join-Path $dataset $name))) { throw "演示素材缺失：$name" }
}
foreach ($folder in @($destinationFull,(Join-Path $destinationFull 'plugins'),
        (Join-Path $destinationFull 'config'),(Join-Path $destinationFull 'reports'),
        (Join-Path $destinationFull 'screenshots'),(Join-Path $destinationFull 'DemoDataset_Final'))) {
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
}
Copy-Item -LiteralPath $jar -Destination (Join-Path $destinationFull 'FloodGuard.jar')
Copy-Item -LiteralPath $jar -Destination (Join-Path $destinationFull 'plugins\mapgis-floodguard-plugin.jar')
Get-ChildItem -LiteralPath $dataset -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $destinationFull 'DemoDataset_Final')
}
Copy-Item -LiteralPath (Join-Path $repository 'README.md') -Destination (Join-Path $destinationFull 'README.md')
Copy-Item -LiteralPath (Join-Path $repository 'DemoScript.md') -Destination (Join-Path $destinationFull 'DemoScript.md')
$environmentCheck = Join-Path $repository 'outputs\environment_check.json'
if (Test-Path -LiteralPath $environmentCheck) {
    Copy-Item -LiteralPath $environmentCheck -Destination (Join-Path $destinationFull 'config\environment_check.json')
}
$acceptance = Join-Path $repository 'final_acceptance_report.md'
if (Test-Path -LiteralPath $acceptance) {
    Copy-Item -LiteralPath $acceptance -Destination (Join-Path $destinationFull 'reports\final_acceptance_report.md')
}
@'
# This is a MapGIS host plugin, not a standalone desktop executable.
# Set the MapGIS installation directory and launch the licensed official host.
floodguard.mapgis.home=C:/Program Files/MapGIS 10/Program
floodguard.environment.report=outputs/environment_check.json
'@ | Set-Content -LiteralPath (Join-Path $destinationFull 'config\environment.properties') -Encoding utf8
@'
No project-code redistribution license has been supplied by the rights holder.
This notice does not grant a software license. Obtain a license decision before public distribution.
Bundled SpaceNet 8 imagery is attributed in DemoDataset_Final/README.md and is subject to CC BY-SA 4.0.
MapGIS SDK and runtime are third-party software and are not included in this package.
'@ | Set-Content -LiteralPath (Join-Path $destinationFull 'LICENSE') -Encoding utf8
'真实 MapGIS 宿主演练成功后，才可放入本次生成的七张验收截图。当前目录为空。' |
    Set-Content -LiteralPath (Join-Path $destinationFull 'screenshots\README.txt') -Encoding utf8
'真实一键演练成功后，才可放入 FloodGuard_Final_Report.html 和 JSON 证据。当前目录不含示例伪报告。' |
    Set-Content -LiteralPath (Join-Path $destinationFull 'reports\README.txt') -Encoding utf8
$files = Get-ChildItem -LiteralPath $destinationFull -File -Recurse | ForEach-Object {
    [ordered]@{ path = [System.IO.Path]::GetRelativePath($destinationFull,$_.FullName).Replace('\','/');
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant();
                bytes = $_.Length }
}
[ordered]@{ schema_version = 1; competition_acceptance_passed = $false;
            reason = 'MapGIS host GUI and complete native demo have not been verified'; files = @($files) } |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $destinationFull 'release-manifest.json') -Encoding utf8
Write-Host "Curated release staging created: $destinationFull"
