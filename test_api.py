"""
后端 API 测试脚本（对应报告"测试与结果"章节）
运行方式：先启动 python app.py，再另开终端执行 python test_api.py
"""
import unittest
import requests

BASE = "http://localhost:5000"
ADDR = "0x1111111111111111111111111111111111111111"  # 演示地址（仅离线登记）
BAD_ADDR = "not-an-address"


class ApiTests(unittest.TestCase):
    """后端接口测试（链上部分由合约测试覆盖）"""

    def test_01_health(self):
        r = requests.get(f"{BASE}/api/health", timeout=5)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_02_list_scholarships(self):
        r = requests.get(f"{BASE}/api/scholarships", timeout=5)
        self.assertEqual(r.status_code, 200)
        self.assertIn("data", r.json())

    def test_03_register_valid_student(self):
        r = requests.post(f"{BASE}/api/students/register", json={
            "address": ADDR, "name": "张三", "studentId": "20260001"
        }, timeout=5)
        self.assertIn(r.status_code, (200, 201))

    def test_04_register_invalid_address(self):
        r = requests.post(f"{BASE}/api/students/register", json={
            "address": BAD_ADDR, "name": "李四"
        }, timeout=5)
        self.assertEqual(r.status_code, 400)

    def test_05_register_missing_name(self):
        r = requests.post(f"{BASE}/api/students/register", json={
            "address": ADDR, "name": ""
        }, timeout=5)
        self.assertEqual(r.status_code, 400)

    def test_06_apply_unregistered_student(self):
        r = requests.post(f"{BASE}/api/scholarships/0/apply", json={
            "address": "0x2222222222222222222222222222222222222222"
        }, timeout=5)
        self.assertEqual(r.status_code, 403)

    def test_07_apply_registered_student(self):
        r = requests.post(f"{BASE}/api/scholarships/0/apply", json={
            "address": ADDR
        }, timeout=5)
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.json())

    def test_08_apply_nonexistent_scholarship(self):
        r = requests.post(f"{BASE}/api/scholarships/999/apply", json={
            "address": ADDR
        }, timeout=5)
        self.assertIn(r.status_code, (400, 404))

    def test_09_transactions_invalid_address(self):
        r = requests.get(f"{BASE}/api/transactions?address={BAD_ADDR}", timeout=5)
        self.assertEqual(r.status_code, 400)

    def test_10_transactions_valid_address(self):
        r = requests.get(f"{BASE}/api/transactions?address={ADDR}", timeout=5)
        self.assertEqual(r.status_code, 200)
        self.assertIn("data", r.json())


if __name__ == "__main__":
    unittest.main(verbosity=2)