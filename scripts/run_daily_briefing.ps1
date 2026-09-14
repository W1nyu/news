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

# Keep a bounded log so scheduled runs can be diagnosed without Task Scheduler history.
$logDir = Join-Path $projectRoot 'logs'
$logFile = Join-Path $logDir 'collector.log'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
if ((Test-Path -LiteralPath $logFile) -and (Get-Item -LiteralPath $logFile).Length -gt 1MB) {
    Get-Content -LiteralPath $logFile -Tail 2000 | Set-Content -LiteralPath $logFile -Encoding UTF8
}
$stamp = Get-Date -Format 's'
Add-Content -LiteralPath $logFile -Encoding UTF8 -Value "[$stamp] start $($MyInvocation.BoundParameters.Keys -join ',')"
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $python.Source (Join-Path $PSScriptRoot 'collector.py') 2>&1 | ForEach-Object {
    $line = "$_"
    Write-Host $line
    Add-Content -LiteralPath $logFile -Encoding UTF8 -Value "[$stamp] $line"
}
$collectExit = $LASTEXITCODE
$ErrorActionPreference = $previousPreference
Add-Content -LiteralPath $logFile -Encoding UTF8 -Value "[$stamp] exit $collectExit"
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
