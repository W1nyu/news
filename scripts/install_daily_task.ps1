param(
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')]
    [string]$Time = '07:30'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$taskName = 'Daily Economy Briefing'
$runner = Join-Path $PSScriptRoot 'run_daily_briefing.ps1'
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""

schtasks.exe /Create /TN $taskName /TR "powershell.exe $arguments" /SC DAILY /ST $Time /F | Out-Host
Write-Host "'$taskName' 작업을 매일 $Time 에 등록했습니다."
