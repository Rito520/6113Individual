"""
链上数据访问层：封装 web3.py，提供合约读取与事件索引
"""
import json
import logging
import os
import time
from typing import List, Optional, Dict, Any

from web3 import Web3
from web3.middleware import geth_poa_middleware

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- 合约 ABI ----------
# 优先读取编译器产物 build/ScholarshipDistributor.abi。
# 手写 ABI 极易漏掉 event 定义，会导致 contract.events.<Name> 取不到对象、
# 事件索引静默失效（本项目曾因此让「交易历史」永远空白且日志无报错）。
_ABI_PATH = os.path.join(BASE_DIR, "build", "ScholarshipDistributor.abi")

# 兜底 ABI：仅在编译产物缺失或损坏时使用，已包含全部 7 个事件定义
_FALLBACK_ABI = [
    # ---- 事件（索引线程依赖，缺一不可）----
    {"anonymous": False, "name": "ScholarshipCreated", "type": "event", "inputs": [
        {"indexed": True, "name": "id", "type": "uint256"},
        {"indexed": False, "name": "name", "type": "string"},
        {"indexed": False, "name": "totalAmount", "type": "uint256"},
        {"indexed": False, "name": "maxAward", "type": "uint256"},
        {"indexed": False, "name": "studentLimit", "type": "uint256"}]},
    {"anonymous": False, "name": "StudentRegistered", "type": "event", "inputs": [
        {"indexed": True, "name": "student", "type": "address"}]},
    {"anonymous": False, "name": "ApplicationSubmitted", "type": "event", "inputs": [
        {"indexed": True, "name": "scholarshipId", "type": "uint256"},
        {"indexed": True, "name": "student", "type": "address"}]},
    {"anonymous": False, "name": "RecipientApproved", "type": "event", "inputs": [
        {"indexed": True, "name": "scholarshipId", "type": "uint256"},
        {"indexed": True, "name": "student", "type": "address"},
        {"indexed": False, "name": "amount", "type": "uint256"}]},
    {"anonymous": False, "name": "AwardClaimed", "type": "event", "inputs": [
        {"indexed": True, "name": "scholarshipId", "type": "uint256"},
        {"indexed": True, "name": "student", "type": "address"},
        {"indexed": False, "name": "amount", "type": "uint256"},
        {"indexed": False, "name": "timestamp", "type": "uint256"}]},
    {"anonymous": False, "name": "ScholarshipClosed", "type": "event", "inputs": [
        {"indexed": True, "name": "scholarshipId", "type": "uint256"}]},
    {"anonymous": False, "name": "FundsWithdrawn", "type": "event", "inputs": [
        {"indexed": True, "name": "scholarshipId", "type": "uint256"},
        {"indexed": False, "name": "amount", "type": "uint256"}]},

    # ---- 只读查询 ----
    {"inputs": [], "name": "owner", "outputs": [{"name": "", "type": "address"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "scholarshipCount", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "scholarshipId", "type": "uint256"}], "name": "getScholarship",
     "outputs": [
         {"name": "", "type": "tuple",
          "components": [
              {"name": "id", "type": "uint256"},
              {"name": "name", "type": "string"},
              {"name": "totalAmount", "type": "uint256"},
              {"name": "claimedAmount", "type": "uint256"},
              {"name": "maxAward", "type": "uint256"},
              {"name": "studentLimit", "type": "uint256"},
              {"name": "active", "type": "bool"},
              {"name": "recipients", "type": "address[]"}
          ]}
     ], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "scholarshipId", "type": "uint256"}], "name": "getRecipients",
     "outputs": [{"name": "", "type": "address[]"}],
     "stateMutability": "view", "type": "function"},

    # ---- 交易函数（供文档说明，实际签名由 MetaMask 在前端完成）----
    {"inputs": [{"name": "name", "type": "string"}, {"name": "maxAward", "type": "uint256"},
                {"name": "studentLimit", "type": "uint256"}],
     "name": "createScholarship", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "payable", "type": "function"},
    {"inputs": [], "name": "registerStudent", "outputs": [],
     "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "scholarshipId", "type": "uint256"}], "name": "applyForScholarship",
     "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "scholarshipId", "type": "uint256"}, {"name": "student", "type": "address"}],
     "name": "approveRecipient", "outputs": [],
     "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "scholarshipId", "type": "uint256"}], "name": "claimAward",
     "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "scholarshipId", "type": "uint256"}], "name": "closeScholarship",
     "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "scholarshipId", "type": "uint256"}], "name": "withdrawRemaining",
     "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]


def _load_abi() -> List[Dict[str, Any]]:
    """读取完整 ABI（必须含 event 定义）；编译产物缺失或异常时退回内置兜底 ABI"""
    if not os.path.exists(_ABI_PATH):
        logger.warning("未找到编译产物 %s，改用内置兜底 ABI", _ABI_PATH)
        return _FALLBACK_ABI
    try:
        with open(_ABI_PATH, encoding="utf-8") as f:
            abi = json.load(f)
        events = [x for x in abi if x.get("type") == "event"]
        if not events:
            logger.warning("编译产物 ABI 中没有 event 定义，改用内置兜底 ABI")
            return _FALLBACK_ABI
        logger.info("已加载编译产物 ABI：%d 个条目，其中 %d 个 event", len(abi), len(events))
        return abi
    except Exception as e:
        logger.warning("读取编译产物 ABI 失败(%s)，改用内置兜底 ABI", e)
        return _FALLBACK_ABI


SCHOLARSHIP_ABI = _load_abi()

# 事件的「操作者 / 受益者」归属规则。
# 合约事件本身不记录 msg.sender，但 onlyOwner 函数的操作者必然是 owner，
# 因此可据此还原 from(操作者) 与 to(受益者)，让管理员与学生都能查到自己的历史。
_OWNER_EVENTS = {"ScholarshipCreated", "ScholarshipClosed", "FundsWithdrawn"}
_STUDENT_EVENTS = {"StudentRegistered", "ApplicationSubmitted", "AwardClaimed"}
# RecipientApproved 由管理员发起，受益者是学生，单独处理


def _to_hex(value) -> str:
    """统一转成带 0x 前缀的十六进制字符串"""
    s = value.hex() if hasattr(value, "hex") and not isinstance(value, str) else str(value)
    return s if s.startswith("0x") else "0x" + s


class Web3Client:
    """轻量链上客户端：读合约状态、拉取事件"""

    def __init__(self, rpc_url: str, contract_address: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        # Sepolia/Polygon 等网段 PoA 兼容
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.contract = (
            self.w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=SCHOLARSHIP_ABI)
            if contract_address and contract_address != "0x" + "0" * 40 else None
        )
        self.rpc_url = rpc_url
        self._owner_cache: Optional[str] = None

    def is_connected(self) -> bool:
        try:
            return bool(self.w3.is_connected())
        except Exception:
            return False

    # ---------- 合约只读 ----------
    def get_scholarship_count(self) -> int:
        if self.contract is None:
            return 0
        return self.contract.functions.scholarshipCount().call()

    def get_scholarship(self, scholarship_id: int) -> Optional[Dict[str, Any]]:
        if self.contract is None:
            return None
        try:
            s = self.contract.functions.getScholarship(scholarship_id).call()
            return {
                "id": s[0], "name": s[1], "totalAmount": s[2],
                "claimedAmount": s[3], "maxAward": s[4],
                "studentLimit": s[5], "active": s[6], "recipients": s[7]
            }
        except Exception as e:
            logger.warning("读取奖学金 #%s 失败: %s", scholarship_id, e)
            return None

    def get_owner(self) -> Optional[str]:
        """合约管理员地址（带缓存，owner 部署后不会变）"""
        if self.contract is None:
            return None
        if self._owner_cache is None:
            try:
                self._owner_cache = self.contract.functions.owner().call()
            except Exception as e:
                logger.warning("读取 owner 失败: %s", e)
                return None
        return self._owner_cache

    # ---------- 事件索引 ----------
    def fetch_events(self, from_block: str = "latest-minus-500") -> List[Dict[str, Any]]:
        """拉取最近事件（补偿式轮询）。返回统一结构的记录列表。"""
        if self.contract is None:
            return []

        latest = self.w3.eth.block_number
        # 回看窗口可用 EVENT_SCAN_BLOCKS 调整：本地链 500 块≈8 分钟，
        # Sepolia 500 块≈100 分钟；线上建议 5000（≈17 小时）
        scan_blocks = int(os.environ.get("EVENT_SCAN_BLOCKS", "500"))
        start = max(latest - scan_blocks, 0)
        owner = self.get_owner()

        result: List[Dict[str, Any]] = []
        # (事件名, 该事件包含的参数字段名)
        signatures = [
            ("ScholarshipCreated", ["id", "name", "totalAmount", "maxAward", "studentLimit"]),
            ("StudentRegistered", ["student"]),
            ("ApplicationSubmitted", ["scholarshipId", "student"]),
            ("RecipientApproved", ["scholarshipId", "student", "amount"]),
            ("AwardClaimed", ["scholarshipId", "student", "amount", "timestamp"]),
            ("ScholarshipClosed", ["scholarshipId"]),
            ("FundsWithdrawn", ["scholarshipId", "amount"]),
        ]
        event_map = {
            "ScholarshipCreated": "create",
            "StudentRegistered": "register",
            "ApplicationSubmitted": "apply",
            "RecipientApproved": "approve",
            "AwardClaimed": "claim",
            "ScholarshipClosed": "close",
            "FundsWithdrawn": "withdraw",
        }

        for name, args in signatures:
            try:
                method = getattr(self.contract.events, name)
                # web3.py v6 使用驼峰参数名 fromBlock / toBlock
                entries = method.get_logs(fromBlock=start, toBlock="latest")
                for e in entries:
                    ev = e["args"]
                    student = ev.get("student", "") if "student" in args else ""
                    amount = ev.get("amount", 0) if "amount" in args else 0

                    # 还原操作者与受益者
                    if name in _OWNER_EVENTS:
                        actor = owner or ""
                        beneficiary = owner or "" if name == "FundsWithdrawn" else ""
                    elif name == "RecipientApproved":
                        actor = owner or ""       # 管理员认定
                        beneficiary = student     # 学生受益
                    else:  # _STUDENT_EVENTS
                        actor = student
                        beneficiary = student

                    result.append({
                        "type": event_map[name],
                        "event": name,
                        "txHash": _to_hex(e["transactionHash"]),
                        "blockNumber": e["blockNumber"],
                        "from": actor,
                        "to": beneficiary,
                        "student": student,
                        "amount": amount,
                    })
            except AttributeError as e:
                # ABI 缺 event 定义时会走到这里，必须显式报出来
                logger.error("合约 ABI 中缺少事件 %s 的定义: %s", name, e)
            except Exception as e:
                logger.warning("读取事件 %s 失败: %s", name, e)
                continue
        return result
