"""
NVIDIA NIM gRPC 客户端
封装对 whisper-large-v3 的 gRPC 调用
protobuf 序列化/反序列化由 riva.client 库自动完成
"""
import asyncio
import subprocess
import tempfile
from pathlib import Path

import httpx
import riva.client

from app.config import MAX_FILE_SIZE_BYTES, NIM_API_KEY, REQUEST_TIMEOUT_SEC

NIM_FUNCTION_ID = "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"
NIM_SERVER = "grpc.nvcf.nvidia.com:443"

# whisper-large-v3 原生支持的音频格式（魔数检测）
# 其他格式（MP3/M4A/AAC 等）需要 ffmpeg 转码为 WAV
_SUPPORTED_MAGIC = {
    b"RIFF": ".wav",
    b"OggS": ".opus",
    b"fLaC": ".flac",
}


def _detect_format(data: bytes) -> str | None:
    """通过文件头魔数检测音频格式，返回扩展名或 None"""
    for magic, ext in _SUPPORTED_MAGIC.items():
        if data[:4].startswith(magic):
            return ext
    return None


def _transcode_to_wav(data: bytes) -> bytes:
    """
    用 ffmpeg 将非原生支持的格式（MP3/M4A/AAC 等）转为 WAV
    WAV 参数：16kHz 采样率、单声道、16-bit PCM（与 NIM 要求一致）
    """
    with tempfile.NamedTemporaryFile(suffix=".input", delete=False) as src:
        src.write(data)
        src_path = Path(src.name)

    dst_path = src_path.parent / f"{src_path.name}.wav"
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src_path),
                "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                str(dst_path),
            ],
            capture_output=True,
            check=True,
            timeout=30,  # ffmpeg 转码超时
        )
        return dst_path.read_bytes()
    finally:
        src_path.unlink(missing_ok=True)
        dst_path.unlink(missing_ok=True)


def _prepare_audio(data: bytes) -> bytes:
    """
    检查音频格式，非原生支持（WAV/OPUS/FLAC）则用 ffmpeg 转码
    返回符合 NIM 要求的音频 bytes
    """
    fmt = _detect_format(data)
    if fmt is not None:
        return data  # 原生支持的格式，直接传
    # 非原生支持格式，需要转码
    return _transcode_to_wav(data)


class NimClient:
    def __init__(self) -> None:
        auth = riva.client.Auth(
            use_ssl=True,
            uri=NIM_SERVER,
            metadata_args=[
                ("function-id", NIM_FUNCTION_ID),
                ("authorization", f"Bearer {NIM_API_KEY}"),
            ],
        )
        self._asr = riva.client.ASRService(auth)

    async def transcribe(self, file_data: bytes, filename: str) -> dict:
        # 音频格式检测与转码：非 WAV/OPUS/FLAC 格式用 ffmpeg 转为 WAV
        file_data = await asyncio.get_running_loop().run_in_executor(
            None, _prepare_audio, file_data
        )
        # [gRPC 序列化] RecognitionConfig 和音频 bytes 由 riva.client/protobuf
        # 序列化为 gRPC 二进制帧，通过 HTTP/2 发往 NVIDIA NVCF 服务器
        config = riva.client.RecognitionConfig(
            language_code="en-US",
            max_alternatives=1,
            enable_automatic_punctuation=True,
            verbatim_transcripts=True,
        )
        # gRPC 是同步阻塞调用，放到线程池执行，避免阻塞 FastAPI 事件循环
        loop = asyncio.get_running_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, self._asr.offline_recognize, file_data, config),
            timeout=REQUEST_TIMEOUT_SEC,
        )
        # [gRPC 反序列化] NVIDIA 返回的 protobuf 二进制响应已被 riva.client
        # 解码为 Python 对象。从 results.alternatives 中提取转写文本
        text = ""
        for result in response.results:
            for alt in result.alternatives:
                if alt.transcript:
                    text += alt.transcript
        return {"text": text.strip()}

    async def transcribe_from_url(self, audio_url: str) -> dict:
        # 先从公网 URL 下载音频文件到内存 bytes
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SEC) as client:
            dl_resp = await client.get(audio_url)
            dl_resp.raise_for_status()
            if len(dl_resp.content) > MAX_FILE_SIZE_BYTES:
                raise ValueError(
                    f"文件大小 {len(dl_resp.content) / 1024 / 1024:.1f}MB 超过限制 {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f}MB"
                )
            # 下载完成后走和直接上传相同的转写流程（含格式检测和转码）
            return await self.transcribe(dl_resp.content, filename="audio_from_url")
