[CmdletBinding()]
param([switch]$KeepOpen)

$ErrorActionPreference = 'Stop'
$program = 'C:\Program Files\MapGIS 10\Program'
$java = Join-Path $program 'java\jre21\bin\java.exe'
$launcher = Join-Path $program 'mapgis_ribbonapploader.jar'
$licenseRoot = 'C:\Program Files\MapGIS 10\license'
if (-not (Test-Path -LiteralPath $java) -or -not (Test-Path -LiteralPath $launcher)) {
    throw 'MapGIS Java 21 Ribbon host is not installed.'
}
if (-not (Test-Path -LiteralPath $licenseRoot) -or -not (Get-ChildItem -LiteralPath $licenseRoot -Filter '*.lic' -ErrorAction SilentlyContinue)) {
    throw "MapGIS Objects Java license is missing under $licenseRoot. See BLOCKERS.md."
}

$arguments = @('-Dfile.encoding=UTF-8', '-cp', '*;lib/*', 'com.zondy.mapgis.ribbonapploader.DesktopLauncher')
$process = Start-Process -FilePath $java -ArgumentList $arguments -WorkingDirectory $program -PassThru
if (-not $KeepOpen) {
    Start-Sleep -Seconds 10
    if ($process.HasExited) { throw "MapGIS Java host exited early with code $($process.ExitCode)." }
    Stop-Process -Id $process.Id
}
Write-Host 'MapGIS Java host authorization and startup verified.'
