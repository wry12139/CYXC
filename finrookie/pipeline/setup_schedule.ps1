# Windows Task Scheduler 配置脚本
# 管理员权限运行此脚本来配置每日早报更新

# 任务参数
$TaskName = "FinRookie-DailyBriefingUpdate"
$ScriptPath = "C:\Users\86184\finrookie\pipeline\daily_update.sh"
$BashPath = "C:\Program Files\Git\bin\bash.exe"  # Git Bash 路径

# 检查是否以管理员权限运行
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ 需要管理员权限。请以管理员身份运行此脚本。"
    exit 1
}

# 定义任务触发器（每天 0:00 和 6:00）
$trigger1 = New-ScheduledTaskTrigger -Daily -At 00:00
$trigger2 = New-ScheduledTaskTrigger -Daily -At 06:00
$triggers = @($trigger1, $trigger2)

# 定义任务动作
$action = New-ScheduledTaskAction -Execute $BashPath -Argument "-c `"$ScriptPath`""

# 定义任务设置
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -RunWithoutNetwork -StartWhenAvailable

# 创建或更新任务
try {
    # 尝试移除已有任务
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # 创建新任务
    Register-ScheduledTask -TaskName $TaskName `
        -Action $action `
        -Trigger $triggers `
        -Settings $settings `
        -Description "FinRookie 每日早报自动更新（0:00 和 6:00）" `
        -RunLevel Highest

    Write-Host "✅ 定时任务已创建成功！"
    Write-Host "任务名称: $TaskName"
    Write-Host "执行时间: 每天 00:00 和 06:00"
    Write-Host "脚本路径: $ScriptPath"

} catch {
    Write-Host "❌ 错误: $_"
    exit 1
}
