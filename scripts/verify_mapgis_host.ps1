[CmdletBinding()]
param([switch]$KeepOpen, [ValidateSet('Developer', 'Product')][string]$Mode = 'Developer')

$ErrorActionPreference = 'Stop'
$program = 'C:\Program Files\MapGIS 10\Program'
$java = Join-Path $program 'java\jre21\bin\java.exe'
$launcher = Join-Path $program 'mapgis_ribbonapploader.jar'
if (-not (Test-Path -LiteralPath $java) -or -not (Test-Path -LiteralPath $launcher)) {
    throw 'MapGIS Java 21 Ribbon host is not installed.'
}
$root = Split-Path $PSScriptRoot -Parent
$logDir = Join-Path $root 'logs\mapgis-host'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$stdout = Join-Path $logDir "$stamp.stdout.log"
$stderr = Join-Path $logDir "$stamp.stderr.log"
# Mirror the installed official developer launcher; never alter licensing state.
$arguments = @('--add-opens', 'java.base/java.net=ALL-UNNAMED')
foreach ($export in @(
    'javafx.base/com.sun.javafx.collections', 'javafx.base/com.sun.javafx.event',
    'javafx.graphics/com.sun.glass.ui', 'javafx.graphics/com.sun.javafx.application',
    'javafx.graphics/com.sun.javafx.scene.input', 'javafx.graphics/com.sun.javafx.util',
    'javafx.controls/com.sun.javafx.scene.control', 'javafx.controls/com.sun.javafx.scene.control.behavior',
    'javafx.controls/com.sun.javafx.scene.control.skin', 'javafx.controls/com.sun.javafx.scene.control.skin.resources',
    'javafx.web/com.sun.javafx.webkit', 'javafx.web/com.sun.webkit')) {
    $arguments += @('--add-exports', "$export=ALL-UNNAMED")
}
$arguments += @('-Dfile.encoding=UTF-8', '-Dmapgis.console.encoding=UTF-8', '-cp', '*;lib/*',
    'com.zondy.mapgis.ribbonapploader.DesktopLauncher')
if ($Mode -eq 'Developer') { $arguments += '--developer' }
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run setup_python.ps1 first.' }
$helperArgs = @('--java', $java, '--program', $program, '--stdout', $stdout, '--stderr', $stderr)
if ($KeepOpen) { $helperArgs += '--keep-open' }
# Capture raw bytes: native SDK emits GBK, Java logger may emit UTF-8.
& $python (Join-Path $PSScriptRoot 'verify_mapgis_host.py') @helperArgs -- @arguments
if ($LASTEXITCODE -ne 0) { throw "MapGIS host verification not passed (code $LASTEXITCODE). See $logDir and BLOCKERS.md." }
