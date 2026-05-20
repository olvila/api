"""
测试上传两个文件 — 验证多文件行为
需求规定仅支持单次上传单个文件，传多个时应只处理一个
"""
import requests

URL = "http://localhost:8008/v1/audio/transcriptions"

with open("tests/test_audio.wav", "rb") as f:
    audio1 = f.read()
with open("/tmp/asr_test_files/test.wav", "rb") as f:
    audio2 = f.read()

print("=== 测试1: 上传两个 file 字段 ===")
resp = requests.post(URL, files=[
    ("file", ("audio1.wav", audio1)),
    ("file", ("audio2.wav", audio2)),
], timeout=65)
print(f"状态码: {resp.status_code}")
print(f"响应: {resp.json()}")

print("\n=== 测试2: 上传单个 file 字段(对照组) ===")
resp = requests.post(URL, files={"file": ("audio1.wav", audio1)}, timeout=65)
print(f"状态码: {resp.status_code}")
print(f"响应: {resp.json()}")
