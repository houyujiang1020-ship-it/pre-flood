[CmdletBinding()]
param(
    [string]$Jdk21 = 'C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot',
    [string]$MapGisProgram = 'C:\Program Files\MapGIS 10\Program'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$maven = Join-Path $projectRoot 'tools\apache-maven-3.9.16'

foreach ($required in @(
    (Join-Path $jdk21 'bin\javac.exe'),
    (Join-Path $maven 'bin\mvn.cmd'),
    (Join-Path $mapgisProgram 'mapgis_pluginengine.jar'),
    (Join-Path $mapgisProgram 'mapgis_geomap.jar'),
    (Join-Path $mapgisProgram 'mapgis_geoobjects.jar'),
    (Join-Path $mapgisProgram 'mapgis_geodatabase.jar'),
    (Join-Path $mapgisProgram 'mapgis_geoanalysis.jar'),
    (Join-Path $mapgisProgram 'mapgis_ui_controls.jar'))) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required MapGIS build dependency is missing: $required" }
}

$env:JAVA_HOME = $jdk21
$env:MAVEN_HOME = $maven
$env:Path = "$env:JAVA_HOME\bin;$env:MAVEN_HOME\bin;$env:Path"
$env:JAVA_TOOL_OPTIONS = '-Dfile.encoding=UTF-8'
Push-Location -LiteralPath (Join-Path $projectRoot 'app\mapgis-flood-desktop')
try {
    mvn -Pmapgis-sdk '-Dmaven.compiler.release=21' "-Dmapgis.home=$MapGisProgram" clean package
    if ($LASTEXITCODE -ne 0) { throw "MapGIS plugin build failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

$artifact = Join-Path $projectRoot 'app\mapgis-flood-desktop\target\mapgis-floodguard-plugin.jar'
if (-not (Test-Path -LiteralPath $artifact)) { throw "Plugin artifact was not created: $artifact" }
Write-Host "MapGIS plugin built: $artifact"
