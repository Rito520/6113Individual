"""
奖学金分发系统 DApp — Flask 后端主程序
"""
import os
import threading
import time

from flask import Flask, jsonify, request
from flask_cors import CORS

from models import db, ScholarshipRecord, StudentRecord, TransactionRecord
from web3_client import Web3Client

app = Flask(__name__)
CORS(app)

# ---------- 配置 ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "scholarship.db")
# 默认用项目内 SQLite；设置了 DATABASE_URL 则优先使用（Render 上可选接 Postgres）。
# 注意：Render 免费版文件系统是临时的，SQLite 数据在每次重启/重新部署后都会丢失；
# 本项目数据以链上为准、本地库只是缓存，所以重启后会自动重建，不影响演示。
DB_URI = os.environ.get("DATABASE_URL") or f"sqlite:///{DB_PATH}"
if DB_URI.startswith("postgres://"):
    # SQLAlchemy 2.x 不再接受 postgres:// 前缀（Render 默认给的就是它）
    DB_URI = DB_URI.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000")
RPC_URL = os.environ.get("RPC_URL", "https://rpc.sepolia.org")

db.init_app(app)
w3_client = Web3Client(RPC_URL, CONTRACT_ADDRESS)

# ---------- 辅助操作 ----------
def to_eth(wei):
    """wei -> ETH（精度取舍）"""
    return round(wei / 10 ** 18, 6)


def to_wei(eth_amount):
    """ETH -> wei（输入校验）"""
    try:
        eth_amount = float(eth_amount)
    except (TypeError, ValueError):
        raise ValueError("金额格式不正确")
    if eth_amount <= 0:
        raise ValueError("金额必须大于 0")
    return int(eth_amount * 10 ** 18)


def sync_scholarships_from_chain() -> bool:
    """将链上奖学金项目同步到本地 SQLite（供列表页展示）

    返回 True 表示本次成功读到链上数据，False 表示链不可用（降级离线）。
    仅在成功读到链上数据时才清理本地多余缓存，避免链短暂不可用时误删。
    """
    if w3_client.contract is None:
        # 未配置合约地址：对链上状态一无所知，既不能同步、
        # 也绝不能据 count=0 清理缓存（否则会把整个列表误删）
        return False
    try:
        count = w3_client.get_scholarship_count()
        for i in range(count):
            sch = w3_client.get_scholarship(i)
            if sch is None:
                continue
            rec = db.session.get(ScholarshipRecord, i)
            if rec is None:
                rec = ScholarshipRecord(
                    id=i, name=sch["name"], total_amount=to_eth(sch["totalAmount"]),
                    claimed_amount=to_eth(sch["claimedAmount"]), max_award=to_eth(sch["maxAward"]),
                    student_limit=sch["studentLimit"], active=sch["active"]
                )
                db.session.add(rec)
            else:
                rec.name = sch["name"]
                rec.total_amount = to_eth(sch["totalAmount"])
                rec.claimed_amount = to_eth(sch["claimedAmount"])
                rec.max_award = to_eth(sch["maxAward"])
                rec.student_limit = sch["studentLimit"]
                rec.active = sch["active"]

        # 清理链上已不存在的残留缓存（例如本地链重启后数据清空、
        # 或沿用了旧数据库），否则列表会显示早已不存在的项目
        stale = ScholarshipRecord.query.filter(ScholarshipRecord.id >= count).all()
        for rec in stale:
            app.logger.info("清理残留缓存：项目 #%s「%s」链上已不存在", rec.id, rec.name)
            db.session.delete(rec)

        db.session.commit()
        return True
    except Exception as e:  # 链不可用时离线模式
        db.session.rollback()
        app.logger.warning("链上同步失败(降级离线): %s", e)
        return False


def setup_initial_data():
    with app.app_context():
        db.create_all()
        sync_scholarships_from_chain()
        # 不再插入任何示例数据：列表完全以链上真实状态为准。
        # 原实现在库为空时硬编码一条「学术卓越奖学金 5 ETH」，但链上并不存在
        # 该项目，演示时会凭空出现一笔无主资金，无法自圆其说。
        if ScholarshipRecord.query.count() == 0:
            app.logger.info("链上暂无奖学金项目，列表为空属正常状态，创建后即显示")


# ---------- 前端页面托管 ----------
@app.route("/")
def index():
    return app.send_static_file("index.html")


# ---------- API ----------
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": time.time()})


@app.route("/api/config", methods=["GET"])
def get_config():
    """向前端下发链配置。

    合约地址不再硬编码在 static/app.js 里：本地测试链每次重启都会清空数据、
    必须重新部署，地址随之改变，硬编码会导致每次都要手改源码。
    改由此处统一下发，部署脚本写入地址后前端自动生效。
    """
    deployed = False
    if CONTRACT_ADDRESS and CONTRACT_ADDRESS != "0x" + "0" * 40:
        deployed = w3_client.contract is not None
    return jsonify({
        "contractAddress": CONTRACT_ADDRESS,
        "rpcUrl": RPC_URL,
        "chainId": int(os.environ.get("CHAIN_ID", "31337")),
        "deployed": deployed,
        "chainConnected": w3_client.is_connected(),
    })


@app.route("/api/scholarships", methods=["GET"])
def list_scholarships():
    """返回全部奖学金项目（每次请求都与链上对齐）

    原实现只在进程启动时同步一次链上数据，之后索引线程仅写 transactions 表、
    从不刷新 scholarships 表，导致「前端创建项目成功但列表不出现新项目」。
    这里改为每次请求都同步一次；本地链秒级出块，开销可忽略。
    """
    sync_scholarships_from_chain()
    rows = ScholarshipRecord.query.order_by(ScholarshipRecord.id).all()
    data = [{
        "id": r.id, "name": r.name, "totalAmount": r.total_amount,
        "claimedAmount": r.claimed_amount, "maxAward": r.max_award,
        "studentLimit": r.student_limit, "active": r.active
    } for r in rows]
    return jsonify({"data": data})


@app.route("/api/students/register", methods=["POST"])
def register_student():
    """学生资料登记（链上身份由 MetaMask 签名保证，此处仅存离线资料）"""
    body = request.get_json(silent=True) or {}
    address = (body.get("address") or "").strip().lower()
    name = (body.get("name") or "").strip()
    student_id = (body.get("studentId") or "").strip()

    if not address.startswith("0x") or len(address) != 42:
        return jsonify({"error": "钱包地址无效"}), 400
    if not name:
        return jsonify({"error": "姓名不能为空"}), 400

    rec = StudentRecord.query.filter_by(address=address).first()
    if rec is None:
        rec = StudentRecord(address=address, name=name, student_id=student_id)
        db.session.add(rec)
    else:
        rec.name = name
        rec.student_id = student_id
    db.session.commit()
    return jsonify({"ok": True, "address": address}), 201


@app.route("/api/scholarships/<int:scholarship_id>/apply", methods=["POST"])
def apply_voucher(scholarship_id):
    """生成带一次性的申请预审令牌（防止未注册账户大量提交）"""
    body = request.get_json(silent=True) or {}
    address = (body.get("address") or "").strip().lower()
    if not (address.startswith("0x") and len(address) == 42):
        return jsonify({"error": "钱包地址无效"}), 400

    student = StudentRecord.query.filter_by(address=address).first()
    if student is None:
        return jsonify({"error": "请先完成学生资料登记"}), 403

    # 先与链上对齐：刚创建的项目可能还没进本地缓存，
    # 否则会在链上明明存在的情况下误报「项目不存在」
    sync_scholarships_from_chain()
    sch = db.session.get(ScholarshipRecord, scholarship_id)
    if sch is None:
        return jsonify({"error": "奖学金项目不存在"}), 404
    if not sch.active:
        return jsonify({"error": "项目已关闭"}), 400

    # 一次性令牌：地址+项目+时间戳，前端仅用于跟随后续签名，本身不授权资金
    token = f"voucher-{scholarship_id}-{address}-{int(time.time())}"
    return jsonify({"ok": True, "token": token, "scholarshipId": scholarship_id})


@app.route("/api/transactions", methods=["GET"])
def list_transactions():
    """返回某地址相关的链上交易历史（来自本地索引）"""
    address = (request.args.get("address") or "").strip().lower()
    if not (address.startswith("0x") and len(address) == 42):
        return jsonify({"error": "钱包地址无效"}), 400

    rows = (TransactionRecord.query
            .filter((TransactionRecord.from_address == address) |
                    (TransactionRecord.to_address == address))
            .order_by(TransactionRecord.block_number.desc())
            .limit(100).all())
    data = [{
        "txHash": r.tx_hash, "type": r.tx_type, "blockNumber": r.block_number,
        "amount": r.amount, "status": r.status, "timestamp": r.timestamp
    } for r in rows]
    return jsonify({"data": data})


# ---------- 链上事件索引线程 ----------
def event_indexer():
    """周期性拉取合约事件写入本地库（补偿式同步，兼顾简单与最终一致）"""
    while True:
        try:
            # 线程内数据库操作必须在应用上下文内执行
            with app.app_context():
                events = w3_client.fetch_events(from_block="latest-minus-500")
                for ev in events:
                    tx_hash = ev["txHash"]
                    if TransactionRecord.query.filter_by(tx_hash=tx_hash).first():
                        continue
                    record = TransactionRecord(
                        tx_hash=tx_hash,
                        tx_type=ev["type"],
                        # 链上返回的是校验和大小写地址，而查询接口按小写比对，
                        # 不统一会导致「交易历史」永远查不到记录
                        from_address=(ev.get("from", "") or "").lower(),
                        to_address=(ev.get("to", "") or ev.get("student", "") or "").lower(),
                        block_number=ev["blockNumber"],
                        amount=to_eth(ev.get("amount", 0)),
                        status="confirmed",
                        timestamp=int(time.time())
                    )
                    db.session.add(record)
                db.session.commit()
                if events:
                    app.logger.info("事件索引：本轮读取 %d 条链上事件", len(events))
        except Exception as e:
            app.logger.warning("事件索引异常: %s", e)
        time.sleep(15)  # 每 15 秒补偿一次


# ---------- 启动 ----------
# 初始化必须放在模块级：Render 用 gunicorn 启动（gunicorn app:app），
# app.py 是被 import 的模块，__main__ 分支不会执行；若初始化留在
# __main__ 里，线上会不建表、不启动索引线程。本地 py app.py 两种方式都兼容。
_indexer_started = False


def _bootstrap():
    global _indexer_started
    setup_initial_data()
    if os.environ.get("ENABLE_INDEXER", "1") == "1" and not _indexer_started:
        _indexer_started = True
        t = threading.Thread(target=event_indexer, daemon=True)
        t.start()


_bootstrap()

if __name__ == "__main__":
    # Render 会注入 PORT 环境变量；本地默认 5000
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)