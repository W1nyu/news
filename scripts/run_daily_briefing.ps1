param(
    [switch]$Open,
    [switch]$IfMissing
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

if ($IfMissing) {
    $kstToday = [DateTime]::UtcNow.AddHours(9).ToString('yyyy-MM-dd')
    $todayFile = Join-Path $projectRoot "data\$kstToday.json"
    if (Test-Path -LiteralPath $todayFile) {
        Write-Host "오늘($kstToday) 보고서가 이미 있어 수집을 건너뜁니다."
        exit 0
    }
}

$python = Get-Command python -ErrorAction Stop

& $python.Source (Join-Path $PSScriptRoot 'collector.py')
$collectExit = $LASTEXITCODE
if ($collectExit -ne 0 -and -not ($Open -and $collectExit -eq 2)) {
    exit $collectExit
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
        Start-Process -FilePath $python.Source -ArgumentList @((Join-Path $PSScriptRoot 'server.py')) -WorkingDirectory $projectRoot -WindowStyle Hidden
        Start-Sleep -Seconds 1
    }
    Start-Process $siteUrl
}
