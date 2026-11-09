[CmdletBinding()]
param(
    [string]$Jdk21 = 'C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot',
    [string]$MapGisProgram = 'C:\Program Files\MapGIS 10\Program',
    [string]$ArtifactPath
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$classes = Join-Path $projectRoot 'runtime\registration-probe'
$artifact = Join-Path $projectRoot 'app\mapgis-flood-desktop\target\mapgis-floodguard-plugin.jar'
if ($ArtifactPath) { $artifact = (Resolve-Path -LiteralPath $ArtifactPath).Path }
$logConfig = ([uri](Join-Path $PSScriptRoot 'probe-log4j2.xml')).AbsoluteUri
New-Item -ItemType Directory -Path $classes -Force | Out-Null
& (Join-Path $Jdk21 'bin\javac.exe') -proc:none -encoding UTF-8 -cp "$MapGisProgram\*;$MapGisProgram\lib\*" -d $classes (Join-Path $PSScriptRoot 'PluginRegistrationProbe.java')
if ($LASTEXITCODE -ne 0) { throw 'Registration probe compilation failed.' }
$originalPath = $env:PATH
try {
    $env:PATH = "$MapGisProgram;$originalPath"
    & (Join-Path $MapGisProgram 'java\jre21\bin\java.exe') "-Djava.library.path=$MapGisProgram" "-Dlog4j2.configurationFile=$logConfig" -cp "$classes;$MapGisProgram\*;$MapGisProgram\lib\*" PluginRegistrationProbe $artifact
    if ($LASTEXITCODE -ne 0) { throw 'Plugin registration failed in the installed SDK.' }
} finally {
    $env:PATH = $originalPath
}
