[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Pre,
    [Parameter(Mandatory=$true)][string]$Post,
    [Parameter(Mandatory=$true)][string]$Mask,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$ArtifactPath = 'runtime/integrated-build/mapgis-floodguard-plugin.jar',
    [string]$MapGisProgram = 'C:\Program Files\MapGIS 10\Program'
)
$ErrorActionPreference = 'Stop'
$artifact = (Resolve-Path -LiteralPath $ArtifactPath).Path
$prePath = (Resolve-Path -LiteralPath $Pre).Path
$postPath = (Resolve-Path -LiteralPath $Post).Path
$maskPath = (Resolve-Path -LiteralPath $Mask).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Use a new output directory; existing evidence is preserved.' }
$originalPath = $env:PATH
try {
    $env:PATH = "$MapGisProgram;$originalPath"
    Push-Location -LiteralPath $MapGisProgram
    try {
        & (Join-Path $MapGisProgram 'java\jre21\bin\java.exe') "-Djava.library.path=$MapGisProgram" '-Dfile.encoding=UTF-8' -cp "$artifact;$MapGisProgram\*;$MapGisProgram\lib\*" com.mapgis.floodguard.mapgis.NativeRasterAcceptance $prePath $postPath $maskPath $outputPath
    } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "Native raster acceptance failed: exit $LASTEXITCODE. This is not a desktop-rendering or network test." }
} finally { $env:PATH = $originalPath }
