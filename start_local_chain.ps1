<# 本地测试链启动脚本（在小组作业已装好的 Hardhat 目录里启动）
   等价于手动执行：在 SC6113\D-integration\contracts 目录下运行 npx hardhat node --port 8545
   做成脚本的原因：你的终端可能没有把 node/npx 加入 PATH，脚本内部会自动定位：
     1) 优先用 PATH 里的 node
     2) 找不到就用千问工作助理自带的 Node 运行时（已验证可跑 Hardhat 2.29.1）
     3) 都没有才提示你去 nodejs.org 安装
   用法：powershell -ExecutionPolicy Bypass -File start_local_chain.ps1
   注意：本窗口会持续运行并显示 20 个测试账户，不要关闭。 #>
$ErrorActionPreference = 'Stop'

$binDir = $null
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) {
    $binDir = Split-Path -Parent $nodeCmd.Source
    Write-Host "使用 PATH 中的 Node.js：$($nodeCmd.Source)"
} else {
    # 回退：千问工作助理自带的 Node 运行时（含 node/npm/npx 同目录）
    $bundled = Join-Path $env:LOCALAPPDATA 'Qianwen\User Data\qwen-agent\resources\bins'
    if (Test-Path (Join-Path $bundled 'node.exe')) {
        $binDir = $bundled
        $env:Path = "$bundled;$env:Path"
        Write-Host "PATH 中没有 Node.js，改用自带运行时：$bundled"
    } else {
        Write-Host ''
        Write-Host '[错误] 没有检测到 Node.js。' -ForegroundColor Red
        Write-Host '       请到 nodejs.org 下载 LTS 安装包（.msi），一路默认安装，' -ForegroundColor Red
        Write-Host '       装完关闭本窗口、重新打开 PowerShell 再运行本脚本。' -ForegroundColor Red
        Write-Host ''
        exit 1
    }
}
Write-Host "Node.js 版本：$(node --version)"

$dir = 'D:\Documents\qwen-agent\ajBjhW5orS\default\SC6113\D-integration\contracts'
if (-not (Test-Path (Join-Path $dir 'node_modules\hardhat'))) {
    Write-Host "[错误] 未找到小组作业的 Hardhat：$dir" -ForegroundColor Red
    exit 1
}

Write-Host '本地测试链启动中（chainId 31337，20 个账户各 10000 测试 ETH）...'
Write-Host '本窗口不要关闭。另开窗口继续后续步骤。'
Write-Host ''
Set-Location $dir
npx hardhat node --port 8545
