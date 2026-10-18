"""
SQLite 数据模型
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class ScholarshipRecord(db.Model):
    """奖学金项目（本地缓存，最终以链上为准）"""
    __tablename__ = "scholarships"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    total_amount = db.Column(db.Float, default=0.0)      # ETH
    claimed_amount = db.Column(db.Float, default=0.0)    # ETH
    max_award = db.Column(db.Float, default=0.0)         # ETH
    student_limit = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)


class StudentRecord(db.Model):
    """学生离线资料"""
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(42), unique=True, index=True, nullable=False)
    name = db.Column(db.String(64), nullable=False)
    student_id = db.Column(db.String(32), default="")


class TransactionRecord(db.Model):
    """链上交易索引"""
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    tx_hash = db.Column(db.String(66), unique=True, index=True, nullable=False)
    tx_type = db.Column(db.String(32), nullable=False)   # create/register/apply/approve/claim/withdraw
    from_address = db.Column(db.String(42), default="")
    to_address = db.Column(db.String(42), default="")
    amount = db.Column(db.Float, default=0.0)            # ETH
    status = db.Column(db.String(16), default="confirmed")
    block_number = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.Integer, default=0)