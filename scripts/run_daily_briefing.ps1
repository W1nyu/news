param(
    [switch]$Open
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction Stop

& $python.Source (Join-Path $PSScriptRoot 'collector.py')
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($Open) {
    $siteUrl = 'http://127.0.0.1:8765/'
    $isServing = $false
    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri $siteUrl -TimeoutSec 2
        $isServing = $true
    } catch {
        $isServing = $false
    }

    if (-not $isServing) {
        $pythonExe = $python.Source
        Start-Process -FilePath $pythonExe -ArgumentList @((Join-Path $PSScriptRoot 'server.py')) -WorkingDirectory $projectRoot -WindowStyle Hidden
        Start-Sleep -Seconds 1
    }
    Start-Process $siteUrl
}
