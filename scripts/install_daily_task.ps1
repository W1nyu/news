param(
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')]
    [string]$Time = '07:30',
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot 'run_daily_briefing.ps1'
$dailyName = 'Daily Economy Briefing'
$logonName = 'Daily Economy Briefing (Logon)'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) '아침 경제 수집.lnk'
$user = "$env:USERDOMAIN\$env:USERNAME"

if ($Uninstall) {
    foreach ($name in @($dailyName, $logonName)) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
    Write-Host '예약 작업 2개와 바탕화면 바로가기를 제거했습니다.'
    exit 0
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew

$dailyAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`"" -WorkingDirectory $projectRoot
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $Time
Register-ScheduledTask -TaskName $dailyName -Action $dailyAction -Trigger $dailyTrigger -Settings $settings -User $user -Force | Out-Null

$logonAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -IfMissing" -WorkingDirectory $projectRoot
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$logonTrigger.Delay = 'PT1M'
Register-ScheduledTask -TaskName $logonName -Action $logonAction -Trigger $logonTrigger -Settings $settings -User $user -Force | Out-Null

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Open"
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = '아침 경제 뉴스를 지금 수집하고 화면을 엽니다'
$shortcut.Save()

Write-Host "'$dailyName'(매일 $Time), '$logonName'(로그인 1분 후, 오늘 보고서 없을 때만) 작업과 바탕화면 '아침 경제 수집' 바로가기를 등록했습니다."
