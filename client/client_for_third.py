"""
第三方业务系统集成示例 — 对方系统直接传 bytes 调用我们的接口
完整序列化链路见代码中注释

与 client.py 的区别：
  client.py        — 接收文件路径 str，内部 open 后发送（本地测试用）
  client_for_third.py — 直接接收内存中的 bytes（对方系统集成用）
"""
import requests

ASR_API_URL = "http://你的服务器IP:8008/v1/audio/transcriptions"


def call_asr_from_bytes(file_bytes: bytes, filename: str) -> dict:
    """
    接收内存中的文件字节流，调用 ASR 接口
    这是对方系统的主要集成方式：
      对方的用户在对方系统上传文件 → 对方拿到 bytes → 调我们这个函数 → 拿到转写文本
    """
    # [序列化点] requests 库将 (filename, bytes) 元组编码为 multipart/form-data，
    # 放入 HTTP body 发往我们的服务
    resp = requests.post(
        ASR_API_URL,
        files={"file": (filename, file_bytes)},
        timeout=65,
    )
    resp.raise_for_status()
    # [反序列化点] JSON 字符串 → Python dict
    return resp.json()


def call_asr_from_url(audio_url: str) -> dict:
    """通过公网 URL 调用 ASR 接口 — 对方传 URL，我们自己去下载"""
    resp = requests.post(
        ASR_API_URL,
        data={"url": audio_url},
        timeout=65,
    )
    resp.raise_for_status()
    return resp.json()


# ===== 对方系统在不同框架中的集成方式 =====

# --- Django/DRF ---
# 对方的用户在 Django 中上传文件后：
# file_bytes = request.FILES['audio'].read()   # 从请求中拿到 bytes
# filename = request.FILES['audio'].name
# result = call_asr_from_bytes(file_bytes, filename)

# --- Flask ---
# file_bytes = request.files['audio'].read()
# filename = request.files['audio'].filename
# result = call_asr_from_bytes(file_bytes, filename)

# --- FastAPI ---
# file_bytes = await file.read()
# filename = file.filename
# result = call_asr_from_bytes(file_bytes, filename)

# --- 对方已有文件公网 URL ---
# result = call_asr_from_url("https://对方系统.com/uploads/audio.wav")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python3 client_for_third.py <音频文件路径>")
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        result = call_asr_from_bytes(f.read(), sys.argv[1].split("/")[-1])

    if result["result"] == "success":
        print(f"识别结果: {result['text']}")
    else:
        print(f"错误: {result['error']}")
