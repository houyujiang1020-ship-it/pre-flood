[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$mapgisRoot = 'C:\Program Files\MapGIS 10'

Write-Output '=== Windows ==='
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture
Write-Output '=== CPU / RAM ==='
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
Get-CimInstance Win32_ComputerSystem | Select-Object @{Name='TotalRAM_GB';Expression={[math]::Round($_.TotalPhysicalMemory / 1GB, 2)}}
Write-Output '=== Toolchain ==='
foreach ($command in 'git','python','py','java','javac','mvn','nvidia-smi') {
    $resolved = Get-Command $command -ErrorAction SilentlyContinue
    [pscustomobject]@{Command=$command; Available=[bool]$resolved; Path=$resolved.Source}
}
Write-Output '=== MapGIS ==='
[pscustomobject]@{InstallRoot=$mapgisRoot; Exists=Test-Path -LiteralPath $mapgisRoot}
Get-Service -ErrorAction SilentlyContinue | Where-Object {$_.Name -match 'MapGIS|IGS|DataStore|TileStore'} | Select-Object Name, DisplayName, Status
Write-Output '=== Disks ==='
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{Name='UsedGB';Expression={[math]::Round($_.Used/1GB,1)}}, @{Name='FreeGB';Expression={[math]::Round($_.Free/1GB,1)}}
