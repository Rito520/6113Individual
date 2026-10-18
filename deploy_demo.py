# -*- coding: utf-8 -*-
"""
演示用合约部署脚本
在本地测试链上部署 ScholarshipDistributor，打印合约地址并自动生成配置。

用法：
  1) 先在另一个终端启动本地链：powershell -ExecutionPolicy Bypass -File start_local_chain.ps1
  2) 再运行：py deploy_demo.py
"""
import json
import os
import sys

from web3 import Web3

BASE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(BASE, "build")
RPC = "http://127.0.0.1:8545"


def fail(msg):
    print("[错误] " + msg)
    sys.exit(1)


w3 = Web3(Web3.HTTPProvider(RPC))
if not w3.is_connected():
    fail("连不上本地测试链 127.0.0.1:8545\n"
         "       请先另开一个终端执行：powershell -ExecutionPolicy Bypass -File start_local_chain.ps1")

print("[信息] 已连接本地链，chainId =", w3.eth.chain_id)

abi_path = os.path.join(BUILD, "ScholarshipDistributor.abi")
bin_path = os.path.join(BUILD, "ScholarshipDistributor.bin")
if not (os.path.exists(abi_path) and os.path.exists(bin_path)):
    fail("找不到编译产物 build\\ScholarshipDistributor.abi / .bin\n"
         "       这两个文件应随项目存在；若确实缺失，重新编译需要 Node.js 环境（见指南 2.2 节）")

with open(abi_path, encoding="utf-8") as f:
    ABI = json.load(f)
with open(bin_path, encoding="utf-8") as f:
    BIN = f.read().strip()

deployer = w3.eth.accounts[0]
balance = w3.from_wei(w3.eth.get_balance(deployer), "ether")
print("[信息] 部署账户（管理员）=", deployer)
print("[信息] 该账户余额 =", balance, "ETH")

factory = w3.eth.contract(abi=ABI, bytecode=BIN)
tx_hash = factory.constructor().transact({"from": deployer, "gas": 5_000_000})
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

ADDR = receipt["contractAddress"]
print()
print("=" * 62)
print("[成功] 合约已部署")
print("  合约地址 =", ADDR)
print("  部署交易 =", receipt["transactionHash"].hex())
print("  所在区块 =", receipt["blockNumber"])
print("  消耗 gas =", receipt["gasUsed"])
print("=" * 62)

# 保存地址，供启动脚本自动读取
with open(os.path.join(BUILD, "deployed_address.txt"), "w", encoding="utf-8") as f:
    f.write(ADDR)
print()
print("[完成] 地址已写入 build\\deployed_address.txt（启动脚本会自动读取）")

# 生成 .env（注意：app.py 本身不读取 .env，需靠 start_demo.ps1 注入环境变量）
env_path = os.path.join(BASE, ".env")
with open(env_path, "w", encoding="utf-8") as f:
    f.write(f"CONTRACT_ADDRESS={ADDR}\n")
    f.write(f"RPC_URL={RPC}\n")
    f.write("ENABLE_INDEXER=1\n")
print(f"[完成] 已生成 {env_path}")

print()
print("[下一步]")
print("  前端已改为从后端 /api/config 动态读取合约地址，无需手改源码。")
print("  用启动脚本拉起后端即可：")
print("    powershell -ExecutionPolicy Bypass -File start_demo.ps1")
print("  然后浏览器打开 http://localhost:5000")
print()
print("  注意：本地链每次重启都会清空数据，需重新运行本脚本部署；")
print("        start_demo.ps1 会自动读取最新地址，不用手工同步。")
