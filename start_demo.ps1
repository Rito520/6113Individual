<#
  演示环境启动脚本
  作用：读合约地址 -> 清理残留数据库 -> 注入环境变量 -> 启动后端

  前置：本地测试链必须已在运行（另开终端执行 start_local_chain.ps1）
  用法：powershell -File start_demo.ps1
#>

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = 'C:\Users\11585\AppData\Local\Programs\Python\Python39\python.exe'
$chainRpc = 'http://127.0.0.1:8545'

Write-Host '=== [1/4] 检查本地测试链 ===' -ForegroundColor Cyan
$chainUp = $false
for ($i = 0; $i -lt 5; $i++) {
    try {
        $body = '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'
        $r = Invoke-WebRequest -Uri $chainRpc -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $chainUp = $true; break }
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $chainUp) {
    Write-Host '[停止] 本地测试链没在运行。' -ForegroundColor Red
    Write-Host '       请另开一个终端执行：' -ForegroundColor Yellow
    Write-Host '       powershell -ExecutionPolicy Bypass -File start_local_chain.ps1'
    exit 1
}
Write-Host "    本地链已就绪：$chainRpc" -ForegroundColor Green

Write-Host ''
Write-Host '=== [2/4] 读取合约地址 ===' -ForegroundColor Cyan
$addrFile = Join-Path $root 'build\deployed_address.txt'
if (-not (Test-Path $addrFile)) {
    Write-Host '[停止] 找不到 build\deployed_address.txt' -ForegroundColor Red
    Write-Host '       请先执行：py deploy_demo.py' -ForegroundColor Yellow
    exit 1
}
$addr = (Get-Content -LiteralPath $addrFile -Raw).Trim()
if ($addr -eq ('0x' + '0' * 40)) {
    Write-Host '[停止] 合约地址仍是全零，说明还没部署。' -ForegroundColor Red
    Write-Host '       请先执行：py deploy_demo.py' -ForegroundColor Yellow
    exit 1
}
Write-Host "    合约地址：$addr" -ForegroundColor Green

Write-Host ''
Write-Host '=== [3/4] 清理残留数据库 ===' -ForegroundColor Cyan
$dbFile = Join-Path $root 'scholarship.db'
if (Test-Path $dbFile) {
    # 移到回收站而不是永久删除，保留反悔余地
    try {
        Add-Type -AssemblyName Microsoft.VisualBasic
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
            $dbFile, 'OnlyErrorDialogs', 'SendToRecycleBin')
        Write-Host '    旧 scholarship.db 已移入回收站（后端会自动重建）' -ForegroundColor Green
    } catch {
        Write-Host "    [警告] 数据库删除失败：$($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host '    若列表里出现你没创建过的奖学金项目，请手动把 scholarship.db 移走再重启。' -ForegroundColor Yellow
    }
} else {
    Write-Host '    无残留数据库，跳过' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== [4/4] 注入环境变量并启动后端 ===' -ForegroundColor Cyan
$env:CONTRACT_ADDRESS = $addr
$env:RPC_URL = $chainRpc
$env:ENABLE_INDEXER = '1'
Write-Host "    CONTRACT_ADDRESS = $addr"
Write-Host "    RPC_URL          = $chainRpc"
Write-Host "    ENABLE_INDEXER   = 1"
Write-Host ''
Write-Host '    后端启动中... 浏览器打开 http://localhost:5000' -ForegroundColor Green
Write-Host '    停止后端：在本窗口按 Ctrl+C' -ForegroundColor Yellow
Write-Host ''

& $python app.py
