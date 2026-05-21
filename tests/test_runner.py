"""
ASR 语音转文本服务 — 完整测试用例
覆盖：功能/格式/转码/边界/异常/URL/限流
"""
import json
import subprocess
import sys
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread

import requests

BASE_URL = "http://localhost:8008"
TEST_DIR = Path("/tmp/asr_test_files")
HEADERS = {"moi_key": "PhGBOXtN5mrGoOlsGB8Gpt4mCssA276m-IIjn54d1S-Be44vChewIp_d_8t3dQ48mYsV0AEnpj0H74fr"}

# ====== 生成测试文件 ======
def _prepare_test_files():
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    src = TEST_DIR / "source.aiff"
    subprocess.run(["say", "-o", str(src), "this is a format test"], check=True)
    # 原生支持
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", str(src), str(TEST_DIR / "test.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(TEST_DIR / "test.flac")], capture_output=True, check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(TEST_DIR / "test.opus")], capture_output=True, check=True)
    # 需要转码
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(TEST_DIR / "test.mp3")], capture_output=True, check=True)
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(src), str(TEST_DIR / "test.m4a")], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(TEST_DIR / "test.ogg")], capture_output=True, check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", "-c:a", "aac", str(TEST_DIR / "test.aac")], capture_output=True, check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "48000", "-ac", "1", "-c:a", "ac3", str(TEST_DIR / "test.ac3")], capture_output=True, check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", "-c:a", "wmav2", str(TEST_DIR / "test.wma")], capture_output=True, check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(TEST_DIR / "test.tta")], capture_output=True, check=True)

_prepare_test_files()

# ====== 测试用例定义 ======
TEST_CASES = [
    # --- 功能测试 ---
    {"id": "FUNC-01", "category": "功能", "name": "健康检查",
     "method": "GET", "path": "/health", "params": {},
     "expected_status": 200, "expected_result": None},
    {"id": "FUNC-02", "category": "功能", "name": "上传 WAV 文件转写",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.wav"},
     "expected_status": 200, "expected_result": "success"},
    {"id": "FUNC-03", "category": "功能", "name": "缺少参数时返回错误",
     "method": "POST", "path": "/v1/audio/transcriptions", "params": {},
     "expected_status": 400, "expected_result": "error"},
    {"id": "FUNC-04", "category": "功能", "name": "API 文档可访问",
     "method": "GET", "path": "/docs", "params": {},
     "expected_status": 200, "expected_result": None},

    # --- 原生格式测试 ---
    {"id": "FMT-01", "category": "格式-原生", "name": "WAV 格式 (RIFF)",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.wav"},
     "expected_status": 200, "expected_result": "success"},
    {"id": "FMT-02", "category": "格式-原生", "name": "FLAC 格式 (fLaC)",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.flac"},
     "expected_status": 200, "expected_result": "success"},
    {"id": "FMT-03", "category": "格式-原生", "name": "OPUS 格式 (OggS)",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.opus"},
     "expected_status": 200, "expected_result": "success"},

    # --- 转码格式测试 ---
    {"id": "FMT-04", "category": "格式-转码", "name": "MP3 自动转码 (ID3)",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.mp3"},
     "expected_status": 200, "expected_result": "success"},
    {"id": "FMT-05", "category": "格式-转码", "name": "M4A 自动转码 (ftyp)",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.m4a"},
     "expected_status": 200, "expected_result": "success"},
    {"id": "FMT-06", "category": "格式-转码", "name": "OGG 自动转码",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.ogg"},
     "expected_status": 200, "expected_result": "success"},
    {"id": "FMT-07", "category": "格式-转码", "name": "AAC 自动转码",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.aac"},
     "expected_status": 200, "expected_result": "success"},
    {"id": "FMT-08", "category": "格式-转码", "name": "AC3 自动转码",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.ac3"},
     "expected_status": 200, "expected_result": "success"},
    {"id": "FMT-09", "category": "格式-转码", "name": "WMA 自动转码",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.wma"},
     "expected_status": 200, "expected_result": "success"},
    {"id": "FMT-10", "category": "格式-转码", "name": "TTA 自动转码",
     "method": "POST_FILE", "path": "/v1/audio/transcriptions", "params": {"file": "test.tta"},
     "expected_status": 200, "expected_result": "success"},

    # --- URL 模式测试 ---
    {"id": "URL-01", "category": "URL模式", "name": "通过公网 URL 转写",
     "method": "POST_URL", "path": "/v1/audio/transcriptions", "params": {"url_file": "test.wav"},
     "expected_status": 200, "expected_result": "success"},

    # --- 边界测试 ---
    {"id": "BOUND-01", "category": "边界", "name": "空文件上传",
     "method": "POST_DATA", "path": "/v1/audio/transcriptions", "params": {"data": b"", "filename": "empty.wav"},
     "expected_status": 400, "expected_result": "error"},
    {"id": "BOUND-02", "category": "边界", "name": "超大文件校验 (31MB)",
     "method": "POST_DATA", "path": "/v1/audio/transcriptions",
     "params": {"data": b"\x00" * (31 * 1024 * 1024 + 1), "filename": "big.wav"},
     "expected_status": 413, "expected_result": "error"},

    # --- 异常测试 ---
    {"id": "ERROR-01", "category": "异常", "name": "非音频文件上传",
     "method": "POST_DATA", "path": "/v1/audio/transcriptions",
     "params": {"data": b"hello world", "filename": "not_audio.txt"},
     "expected_status": 400, "expected_result": "error"},
    {"id": "ERROR-02", "category": "异常", "name": "不存在的路径",
     "method": "GET", "path": "/not_exist", "params": {},
     "expected_status": 404, "expected_result": None},

    # --- 限流测试 ---
    {"id": "RATE-01", "category": "限流", "name": "高频请求限流 (>30次/分钟)",
     "method": "RATE_LIMIT", "path": "/v1/audio/transcriptions", "params": {"count": 35},
     "expected_status": None, "expected_result": None},
]

# ====== URL 服务器 (用于 URL 模式测试) ======
_url_server: HTTPServer | None = None
_url_port = 18765

def _start_url_server():
    global _url_server
    import os
    os.chdir(str(TEST_DIR))
    _url_server = HTTPServer(("127.0.0.1", _url_port), SimpleHTTPRequestHandler)
    Thread(target=_url_server.serve_forever, daemon=True).start()

def _stop_url_server():
    if _url_server:
        _url_server.shutdown()

# ====== 测试执行 ======
def run_tests():
    results = []
    passed = 0
    failed = 0
    started_at = time.time()

    print("=" * 70)
    print(" ASR 服务集成测试")
    print(f" 目标: {BASE_URL} | 用例: {len(TEST_CASES)} 个")
    print("=" * 70)

    _start_url_server()

    for tc in TEST_CASES:
        tid = tc["id"]
        name = tc["name"]
        cat = tc["category"]
        start_time = time.time()
        resp = None

        try:
            method = tc["method"]
            exp_status = tc["expected_status"]
            exp_result = tc["expected_result"]
            params = tc["params"]

            if method == "GET":
                resp = requests.get(f"{BASE_URL}{tc['path']}", headers=HEADERS, timeout=5)

            elif method == "POST":
                resp = requests.post(f"{BASE_URL}{tc['path']}", headers=HEADERS, timeout=5)

            elif method == "POST_FILE":
                file_path = TEST_DIR / params["file"]
                resp = requests.post(
                    f"{BASE_URL}{tc['path']}",
                    files={"file": (params["file"], file_path.read_bytes())},
                    headers=HEADERS,
                    timeout=65,
                )

            elif method == "POST_DATA":
                resp = requests.post(
                    f"{BASE_URL}{tc['path']}",
                    files={"file": (params["filename"], params["data"])},
                    headers=HEADERS,
                    timeout=65,
                )

            elif method == "POST_URL":
                url = f"http://127.0.0.1:{_url_port}/{params['url_file']}"
                resp = requests.post(
                    f"{BASE_URL}{tc['path']}",
                    data={"url": url},
                    headers=HEADERS,
                    timeout=65,
                )

            elif method == "RATE_LIMIT":
                # 限流测试：快速发送 >30 次请求，检查是否有 429 或 500
                count = params["count"]
                errors = 0
                successes = 0
                file_data = (TEST_DIR / "test.wav").read_bytes()
                for i in range(count):
                    try:
                        r = requests.post(
                            f"{BASE_URL}{tc['path']}",
                            files={"file": ("test.wav", file_data)},
                            headers=HEADERS,
                            timeout=65,
                        )
                        if r.status_code == 200:
                            successes += 1
                        else:
                            errors += 1
                    except Exception:
                        errors += 1
                # 限流判断：成功数 ≤ 30 且至少部分请求被拒绝
                rate_limited = successes <= 30 and errors > 0
                duration_ms = (time.time() - start_time) * 1000
                verdict = "PASS" if rate_limited else "WARN"
                if verdict == "PASS":
                    passed += 1
                else:
                    failed += 1
                result = {
                    "id": tid, "name": name, "category": cat,
                    "verdict": verdict,
                    "status_code": f"ok={successes}/err={errors}/{count}",
                    "expected_status": "限流生效 (≤30次成功)",
                    "body_summary": "limited" if rate_limited else "no-limit",
                    "body_text_preview": f"成功{successes}次, 失败{errors}次",
                    "duration_ms": round(duration_ms, 2),
                }
                results.append(result)
                print(f"  [{verdict}] {tid} {name} (成功{successes}/失败{errors}/{count}, {duration_ms:.0f}ms)")
                continue

            duration_ms = (time.time() - start_time) * 1000

            body = {}
            try:
                body = resp.json()
            except Exception:
                pass

            status_match = resp.status_code == exp_status if exp_status else True
            result_match = True
            if exp_result is not None:
                result_match = body.get("result") == exp_result
            verdict = "PASS" if (status_match and result_match) else "FAIL"

            if verdict == "PASS":
                passed += 1
            else:
                failed += 1

            result = {
                "id": tid, "name": name, "category": cat,
                "verdict": verdict,
                "status_code": resp.status_code,
                "expected_status": exp_status,
                "body_summary": body.get("result", "") if isinstance(body, dict) else "",
                "body_text_preview": body.get("text", body.get("detail", body.get("error", "")))[:80] if isinstance(body, dict) else str(body)[:80],
                "duration_ms": round(duration_ms, 2),
            }
            results.append(result)

            text_preview = result["body_text_preview"][:50] if result["body_text_preview"] else ""
            print(f"  [{verdict}] {tid} {name} ({resp.status_code}, {duration_ms:.0f}ms) {text_preview}")

        except Exception as e:
            failed += 1
            duration_ms = (time.time() - start_time) * 1000
            result = {
                "id": tid, "name": name, "category": cat,
                "verdict": "ERROR",
                "status_code": getattr(resp, "status_code", None),
                "expected_status": exp_status,
                "body_summary": str(e)[:100],
                "body_text_preview": "",
                "duration_ms": round(duration_ms, 2),
            }
            results.append(result)
            print(f"  [ERROR] {tid} {name}: {str(e)[:60]}")

    _stop_url_server()

    total = len(TEST_CASES)
    pass_rate = passed / total * 100 if total > 0 else 0
    total_duration = time.time() - started_at

    print("=" * 70)
    print(f"  通过: {passed}  失败: {failed}  总计: {total}")
    print(f"  通过率: {pass_rate:.1f}%  总耗时: {total_duration:.0f}s")
    print("=" * 70)

    return results, passed, failed, total, total_duration


if __name__ == "__main__":
    results, passed, failed, total, total_duration = run_tests()

    report = {
        "test_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "service": BASE_URL,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": f"{passed / total * 100:.1f}%",
        "total_duration_sec": round(total_duration, 1),
        "results": results,
    }

    report_path = Path(__file__).parent / "test_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n测试报告: {report_path}")

    sys.exit(0 if failed == 0 else 1)
