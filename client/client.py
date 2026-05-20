"""
调用端示例 — 本机测试用
完整序列化链路见代码中注释
"""
import requests


def transcribe_file(file_path: str, base_url: str = "http://localhost:8008") -> dict:
    """上传音频文件，返回转写结果"""
    # [序列化点 1] open(file_path, "rb") 将磁盘文件读为内存中的 bytes 二进制流
    with open(file_path, "rb") as f:
        # [序列化点 2] requests 库的 files 参数自动将 bytes 编码为
        # multipart/form-data 格式（boundary 分隔 + base64/content-disposition 头），
        # 放入 HTTP 请求 body 发往服务端
        resp = requests.post(
            f"{base_url}/v1/audio/transcriptions",
            files={"file": f},
            timeout=65,
        )
    # 检查 HTTP 状态码，非 2xx 抛异常
    resp.raise_for_status()
    # [反序列化点] 服务端返回 JSON 字符串，
    # resp.json() 将其反序列化为 Python dict
    return resp.json()


def transcribe_url(audio_url: str, base_url: str = "http://localhost:8008") -> dict:
    """通过公网 URL 转写音频"""
    resp = requests.post(
        f"{base_url}/v1/audio/transcriptions",
        data={"url": audio_url},  # URL 作为表单字段发送，无需序列化文件
        timeout=65,
    )
    resp.raise_for_status()
    # [反序列化点] JSON → dict
    return resp.json()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python client.py <音频文件路径>")
        print("示例: python client.py test_audio.wav")
        sys.exit(1)

    result = transcribe_file(sys.argv[1])
    if result["result"] == "success":
        print(f'识别结果: {result["text"]}')
    else:
        print(f'错误: {result["error"]}')
