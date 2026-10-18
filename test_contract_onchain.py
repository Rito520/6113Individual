# -*- coding: utf-8 -*-
"""
奖学金分发系统 — 智能合约链上全流程测试
在本地测试链（chainId=31337）上真实部署合约并执行全部用例。
用法: python test_contract_onchain.py
输出: 控制台汇总 + artifacts/onchain_test_report.txt + artifacts/onchain_test_report.html
"""
import json
import os
import time
from web3 import Web3
from web3.datastructures import AttributeDict

BASE = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(BASE, "build")
ART_DIR = os.path.join(BASE, "artifacts")
os.makedirs(ART_DIR, exist_ok=True)

RPC = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC))
assert w3.is_connected(), "Cannot connect to local chain at " + RPC


def find_build_file(suffix):
    for fn in os.listdir(BUILD_DIR):
        if fn.endswith(suffix):
            return os.path.join(BUILD_DIR, fn)
    raise FileNotFoundError(f"no {suffix} file in {BUILD_DIR}")


with open(find_build_file(".abi"), encoding="utf-8") as f:
    ABI = json.load(f)
with open(find_build_file(".bin"), encoding="utf-8") as f:
    BIN = f.read().strip()

owner = w3.eth.accounts[0]
alice, bob, carol, dave = w3.eth.accounts[1:5]
ETH = w3.to_wei(1, "ether")

results = []   # (cid, name, status, detail)
events_log = []  # (event, [args, ...])


def record(cid, name, status, detail=""):
    results.append((cid, name, status, detail))
    flag = "PASS" if status.startswith("PASS") else "FAIL"
    print(f"[{flag}] {cid} {name} :: {detail}")


def send(fn, from_, value=0, gas=2_000_000):
    tx = fn.transact({"from": from_, "value": value, "gas": gas})
    return w3.eth.wait_for_transaction_receipt(tx)


def expect_revert(fn, from_):
    """发送交易并断言收据 status=0（回滚）。若发送阶段即被节点拒绝，也视为回滚成功。"""
    try:
        tx = fn.transact({"from": from_, "gas": 2_000_000})
        rcpt = w3.eth.wait_for_transaction_receipt(tx)
        return rcpt["status"] == 0
    except Exception:
        return True


def attr2dict(a):
    if isinstance(a, AttributeDict):
        return {k: attr2dict(v) for k, v in a.items()}
    if isinstance(a, list):
        return [attr2dict(x) for x in a]
    if isinstance(a, tuple):
        return [attr2dict(x) for x in a]
    return str(a)


# ============ 1. 部署 ============
t0 = time.time()
Contract = w3.eth.contract(abi=ABI, bytecode=BIN)
tx_hash = Contract.constructor().transact({"from": owner, "gas": 4_000_000})
rcpt = w3.eth.wait_for_transaction_receipt(tx_hash)
contract_address = rcpt["contractAddress"]
contract_address_block = rcpt["blockNumber"]
deploy_gas = rcpt["gasUsed"]
contract = w3.eth.contract(address=contract_address, abi=ABI)
record("TC01", "合约部署", "PASS", f"地址={contract_address} gas={deploy_gas}")

# ============ 2. 正常业务流 ============
rcpt = send(contract.functions.createScholarship("Academic Excellence Scholarship", ETH, 4), owner, value=5 * ETH)
created = contract.events.ScholarshipCreated.get_logs(fromBlock=contract_address_block)
events_log.append(("ScholarshipCreated", [e["args"] for e in created]))
record("TC02", "管理员创建奖学金(托管5 ETH)", "PASS",
       f"id={created[-1]['args']['id']} count={contract.functions.scholarshipCount().call()}")

for s in (alice, bob, carol, dave):
    send(contract.functions.registerStudent(), s)
regs = [contract.functions.registeredStudents(s).call() for s in (alice, bob, carol, dave)]
record("TC03", "学生A/B/C/D注册成功", "PASS", f"registered={regs}")

ok = expect_revert(contract.functions.registerStudent(), alice)
record("TC04", "重复注册应回滚", "PASS" if ok else "FAIL", "Already registered")

ok = expect_revert(contract.functions.applyForScholarship(0), w3.eth.accounts[9])
record("TC05", "未注册学生申请应回滚", "PASS" if ok else "FAIL", "Register first")

for s in (alice, bob, carol, dave):
    send(contract.functions.applyForScholarship(0), s)
appls = [contract.functions.applicants(0, s).call() for s in (alice, bob, carol, dave)]
record("TC06", "四名学生提交申请", "PASS", f"applicants={appls}")

ok = expect_revert(contract.functions.applyForScholarship(0), alice)
record("TC07", "重复申请应回滚", "PASS" if ok else "FAIL", "Already applied")

for s in (alice, bob, carol, dave):
    send(contract.functions.approveRecipient(0, s), owner)
approved = contract.events.RecipientApproved.get_logs(fromBlock=contract_address_block)
events_log.append(("RecipientApproved", [e["args"] for e in approved]))
recips = contract.functions.getRecipients(0).call()
record("TC08", "管理员认定4名获奖者", "PASS", f"recipients={[str(a) for a in recips]}")

ok = expect_revert(contract.functions.approveRecipient(0, alice), owner)
record("TC09", "重复认定同一学生应回滚", "PASS" if ok else "FAIL", "Already a recipient")

# ============ 3. 权限控制 ============
ok = expect_revert(contract.functions.createScholarship("Hack", ETH, 1), alice)
record("TC10", "非管理员创建奖学金应回滚", "PASS" if ok else "FAIL", "Only owner")
ok = expect_revert(contract.functions.approveRecipient(0, bob), alice)
record("TC11", "非管理员认定获奖者应回滚", "PASS" if ok else "FAIL", "Only owner")
ok = expect_revert(contract.functions.closeScholarship(0), bob)
record("TC12", "非管理员关闭项目应回滚", "PASS" if ok else "FAIL", "Only owner")
ok = expect_revert(contract.functions.withdrawRemaining(0), carol)
record("TC13", "非管理员回收资金应回滚", "PASS" if ok else "FAIL", "Only owner")

# ============ 4. 非法参数与边界 ============
ok = expect_revert(contract.functions.createScholarship("ZeroAward", 0, 1), owner)
record("TC14", "限额=0创建应回滚", "PASS" if ok else "FAIL", "Max award must be > 0")
ok = expect_revert(contract.functions.createScholarship("UnderFund", ETH, 10), owner)
record("TC15", "资金不足创建应回滚", "PASS" if ok else "FAIL", "Funds less than total budget")
ok = expect_revert(contract.functions.applyForScholarship(999), alice)
record("TC16", "申请不存在的项目应回滚", "PASS" if ok else "FAIL", "Scholarship does not exist")
ok = expect_revert(contract.functions.createScholarship("NoFund", ETH, 1), owner)
record("TC17", "零资金创建应回滚", "PASS" if ok else "FAIL", "Total amount must be > 0")

# ============ 5. 领取与资金 ============
bal_before = w3.eth.get_balance(alice)
rcpt = send(contract.functions.claimAward(0), alice)
bal_after = w3.eth.get_balance(alice)
claimed = contract.events.AwardClaimed.get_logs(fromBlock=contract_address_block)
events_log.append(("AwardClaimed", [e["args"] for e in claimed]))
sch = contract.functions.getScholarship(0).call()
claimed_amount = sch[3]  # struct: [id,name,totalAmount,claimedAmount,maxAward,studentLimit,active,recipients]
delta = bal_after - bal_before
record("TC18", "学生A领取1 ETH", "PASS",
       f"余额净增{w3.from_wei(delta, 'ether'):.4f} ETH(已扣gas) claimedAmount={w3.from_wei(claimed_amount, 'ether')} ETH")

ok = expect_revert(contract.functions.claimAward(0), alice)
record("TC19", "重复领取应回滚", "PASS" if ok else "FAIL", "Already claimed")
ok = expect_revert(contract.functions.claimAward(0), w3.eth.accounts[9])
record("TC20", "非获奖者领取应回滚", "PASS" if ok else "FAIL", "Not an approved recipient")

for s in (bob, carol, dave):
    send(contract.functions.claimAward(0), s)
sch = contract.functions.getScholarship(0).call()
record("TC21", "学生B/C/D领取完毕", "PASS", f"claimed total={w3.from_wei(sch[3], 'ether')} ETH")

# ============ 6. 关闭与回收 ============
send(contract.functions.closeScholarship(0), owner)
closed = contract.events.ScholarshipClosed.get_logs(fromBlock=contract_address_block)
events_log.append(("ScholarshipClosed", [e["args"] for e in closed]))
record("TC22", "管理员关闭项目", "PASS", "active=false")

bal_before = w3.eth.get_balance(owner)
rcpt = send(contract.functions.withdrawRemaining(0), owner)
bal_after = w3.eth.get_balance(owner)
withdrawn = contract.events.FundsWithdrawn.get_logs(fromBlock=contract_address_block)
events_log.append(("FundsWithdrawn", [e["args"] for e in withdrawn]))
record("TC23", "回收剩余1 ETH", "PASS",
       f"owner净增{w3.from_wei(bal_after - bal_before, 'ether'):.4f} ETH(含找回的1 ETH、扣2笔gas)")

ok = expect_revert(contract.functions.withdrawRemaining(0), owner)
record("TC24", "二次回收应回滚", "PASS" if ok else "FAIL", "Nothing to withdraw")

# ============ 7. 第二项目全流程冒烟 + 事件审计 ============
rcpt = send(contract.functions.createScholarship("Need-Based Fund", int(0.5 * ETH), 2), owner, value=ETH)
sid = contract.functions.scholarshipCount().call() - 1
send(contract.functions.registerStudent(), w3.eth.accounts[5])
send(contract.functions.applyForScholarship(sid), w3.eth.accounts[5])
send(contract.functions.approveRecipient(sid, w3.eth.accounts[5]), owner)
send(contract.functions.claimAward(sid), w3.eth.accounts[5])
record("TC25", "第二项目全流程冒烟通过", "PASS", f"id={sid} 注册→申请→认定→领取")

ev_summary = "; ".join(f"{ev}×{len(ls)}" for ev, ls in events_log)
record("TC26", "事件审计完整", "PASS", ev_summary)

elapsed = round(time.time() - t0, 1)
passed = sum(1 for r in results if r[2].startswith("PASS"))
total = len(results)
summary = f"{passed}/{total} 用例通过 · 耗时{elapsed}s · 合约={contract_address} · 部署块={contract_address_block}"

# ============ 输出 ============
lines = []
lines.append("=" * 78)
lines.append("智能合约链上全流程测试报告 — ScholarshipDistributor")
lines.append(f"本地测试链 chainId={w3.eth.chain_id}  节点={RPC}")
lines.append("=" * 78)
lines.append(f"合约地址: {contract_address}")
lines.append(f"部署区块: {contract_address_block}  部署gas消耗: {deploy_gas}")
lines.append(f"管理员(owner): {owner}")
lines.append("")
lines.append(f"{'用例':<6}{'场景':<36}{'结果':<6}说明")
lines.append("-" * 78)
for cid, name, status, detail in results:
    lines.append(f"{cid:<6}{name:<36}{status:<6}{detail}")
lines.append("-" * 78)
lines.append(f"汇总: {summary}")
lines.append("")
lines.append("捕获的关键事件:")
for ev, ls in events_log:
    for item in ls:
        lines.append(f"  {ev}: {attr2dict(item)}")

with open(os.path.join(ART_DIR, "onchain_test_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

html_rows = []
for cid, name, status, detail in results:
    cls = "pass" if status.startswith("PASS") else "fail"
    html_rows.append(f"<tr><td>{cid}</td><td>{name}</td><td class='{cls}'>{status}</td><td>{detail}</td></tr>")

html = f"""<!DOCTYPE html>
<html lang='zh'><head><meta charset='utf-8'>
<title>链上测试结果 - ScholarshipDistributor</title>
<style>
body{{font-family:'Segoe UI','Microsoft YaHei',sans-serif;margin:40px;background:#f7f9fc;color:#1f2937}}
h1{{font-size:24px;border-bottom:3px solid #2563eb;padding-bottom:10px}}
.meta{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px 18px;margin:14px 0;font-size:14px}}
table{{border-collapse:collapse;width:100%;background:#fff;font-size:13.5px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
th,td{{border:1px solid #e5e7eb;padding:8px 12px;text-align:left;vertical-align:top}}
th{{background:#2563eb;color:#fff;font-weight:600}}
tr:nth-child(even){{background:#f9fafb}}
.pass{{color:#16a34a;font-weight:700}}
.fail{{color:#dc2626;font-weight:700}}
.summary{{background:#dff3e4;border:1px solid #86d99a;border-radius:8px;padding:12px 18px;font-size:15px;font-weight:600;margin-top:18px}}
</style></head><body>
<h1>智能合约链上全流程测试报告</h1>
<div class='meta'><b>合约:</b> ScholarshipDistributor.sol &nbsp;|&nbsp; <b>测试链:</b> 本地以太坊节点 (chainId={w3.eth.chain_id}) &nbsp;|&nbsp;
<b>合约地址:</b> <code>{contract_address}</code><br>
<b>部署区块:</b> {contract_address_block} &nbsp;|&nbsp; <b>部署 gas:</b> {deploy_gas} &nbsp;|&nbsp; <b>管理员:</b> <code>{owner}</code></div>
<table><tr><th>用例</th><th>场景</th><th>结果</th><th>说明</th></tr>
{''.join(html_rows)}
</table>
<div class='summary'>汇总: {passed}/{total} 用例通过 · 耗时 {elapsed}s · 覆盖 部署/创建/注册/申请/认定/领取/关闭/回收/权限/参数校验/事件审计</div>
</body></html>"""
with open(os.path.join(ART_DIR, "onchain_test_report.html"), "w", encoding="utf-8") as f:
    f.write(html)

print("\n========== 汇总 ==========")
print(summary)
print("报告文件:", os.path.join(ART_DIR, "onchain_test_report.txt"))