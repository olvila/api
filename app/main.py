import asyncio
import time
from urllib.parse import unquote

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import JSONResponse

from app.config import MAX_FILE_SIZE_BYTES, NIM_API_KEY
from app.logger import log_request, query_logs
from app.nim_client import NimClient

app = FastAPI(title="ASR Service", version="1.0.0")
nim = NimClient()


@app.on_event("startup")
async def startup() -> None:
    if not NIM_API_KEY:
        raise RuntimeError("NIM_API_KEY is not set in .env")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/logs")
async def get_logs(page: int = 1, size: int = 20) -> dict:
    """查询历史转写日志"""
    return query_logs(page=page, size=size)


@app.post("/v1/audio/transcriptions")
async def transcribe(
    request: Request,
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
) -> JSONResponse:
    start_time = time.time()

    # 确定输入来源
    if file and file.filename:
        filename = file.filename
    elif url:
        filename = unquote(url.rsplit("/", 1)[-1].split("?")[0]) or "audio_from_url"
    else:
        return _error(400, "请提供 file (上传文件) 或 url (公网地址)", start_time, "", 0)

    # [反序列化点 1] FastAPI 已将 HTTP body 中的 multipart/form-data 解析为
    # UploadFile 对象。await file.read() 从 multipart 数据中提取出原始 bytes
    if file and file.filename:
        file_data = await file.read()
        file_size = len(file_data)
        if file_size == 0:
            return _error(400, "文件为空，请上传有效的音频文件", start_time, filename, file_size)
        if file_size > MAX_FILE_SIZE_BYTES:
            return _error(
                413,
                f"文件大小 {file_size / 1024 / 1024:.1f}MB 超过限制 {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f}MB",
                start_time,
                filename,
                file_size,
            )
    else:
        file_data = b""
        file_size = 0

    # 调用 NIM (内部走 gRPC protobuf 序列化/反序列化，见 nim_client.py)
    try:
        if file and file.filename:
            result = await nim.transcribe(file_data, filename)
        else:
            assert url is not None
            result = await nim.transcribe_from_url(url)
            file_size = 0  # URL 模式无法提前知晓大小
    except asyncio.TimeoutError:
        return _error(504, "请求超时", start_time, filename, file_size, result="timeout")
    except ValueError as e:
        return _error(400, str(e), start_time, filename, file_size)
    except Exception as e:
        return _error(500, str(e), start_time, filename, file_size)

    duration_ms = (time.time() - start_time) * 1000
    text = result.get("text", "")

    log_request(
        filename=filename,
        file_size_bytes=file_size,
        status="success" if text else "empty",
        result="success",
        text=text,
        duration_ms=duration_ms,
    )

    return JSONResponse(
        content={
            "status_code": 200,
            "result": "success",
            "text": text,
        }  # [序列化点] FastAPI JSONResponse 将 dict 序列化为 JSON 字符串返回
    )


def _error(
    code: int,
    message: str,
    start_time: float,
    filename: str,
    file_size: int,
    result: str = "error",
) -> JSONResponse:
    duration_ms = (time.time() - start_time) * 1000
    log_request(
        filename=filename,
        file_size_bytes=file_size,
        status="timeout" if result == "timeout" else "error",
        result=result,
        text="",
        duration_ms=duration_ms,
        error=message,
    )
    return JSONResponse(
        status_code=code,
        content={
            "status_code": code,
            "result": result,
            "text": "",
            "error": message,
        },
    )
