[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsRoot = Join-Path $projectRoot 'tools'
$jdkRoot = Join-Path $toolsRoot 'jdk-17'
$mavenRoot = Join-Path $toolsRoot 'apache-maven-3.9.16'
$jdkArchive = Join-Path $toolsRoot 'microsoft-jdk-17.0.20.1-windows-x64.zip'
$mavenArchive = Join-Path $toolsRoot 'apache-maven-3.9.16-bin.zip'
$mavenHashFile = "$mavenArchive.sha512"

New-Item -ItemType Directory -Force -Path $toolsRoot | Out-Null
if (-not (Test-Path -LiteralPath $jdkArchive)) {
    curl.exe -L --fail --retry 3 --output $jdkArchive 'https://aka.ms/download-jdk/microsoft-jdk-17.0.20.1-windows-x64.zip'
}
if (-not (Test-Path -LiteralPath $mavenArchive)) {
    curl.exe -L --fail --retry 3 --output $mavenArchive 'https://dlcdn.apache.org/maven/maven-3/3.9.16/binaries/apache-maven-3.9.16-bin.zip'
    curl.exe -L --fail --retry 3 --output $mavenHashFile 'https://dlcdn.apache.org/maven/maven-3/3.9.16/binaries/apache-maven-3.9.16-bin.zip.sha512'
}

if (Test-Path -LiteralPath $mavenHashFile) {
    $expected = (Get-Content -LiteralPath $mavenHashFile -Raw).Trim().Split(' ')[0].ToUpperInvariant()
    $actual = (Get-FileHash -LiteralPath $mavenArchive -Algorithm SHA512).Hash
    if ($actual -ne $expected) { throw 'Apache Maven SHA-512 verification failed.' }
}
if (-not (Test-Path -LiteralPath $jdkRoot)) { New-Item -ItemType Directory -Path $jdkRoot | Out-Null }
if (-not (Get-ChildItem -LiteralPath $jdkRoot -Directory -ErrorAction SilentlyContinue)) {
    Expand-Archive -LiteralPath $jdkArchive -DestinationPath $jdkRoot
}
if (-not (Test-Path -LiteralPath $mavenRoot)) {
    Expand-Archive -LiteralPath $mavenArchive -DestinationPath $toolsRoot
}

$env:JAVA_HOME = (Get-ChildItem -LiteralPath $jdkRoot -Directory | Select-Object -First 1).FullName
$env:MAVEN_HOME = $mavenRoot
$env:Path = "$env:JAVA_HOME\bin;$env:MAVEN_HOME\bin;$env:Path"
$env:JAVA_TOOL_OPTIONS = '-Dfile.encoding=UTF-8'
java -version
javac -version
mvn --version
