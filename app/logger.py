import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"

_logger: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    LOG_DIR.mkdir(exist_ok=True)

    _logger = logging.getLogger("asr_service")
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

    handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "asr.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)

    return _logger


def query_logs(page: int = 1, size: int = 20) -> dict:
    """查询历史请求日志，支持分页"""
    log_files = sorted(LOG_DIR.glob("asr.log*"), reverse=True)
    entries: list[dict] = []

    # 从当前日志文件读取所有 JSON lines
    for f in log_files:
        if f.exists():
            for line in f.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    entries.reverse()  # 最新的在前

    total = len(entries)
    start = (page - 1) * size
    end = start + size
    page_entries = entries[start:end]

    return {
        "total": total,
        "page": page,
        "size": size,
        "entries": page_entries,
    }


def log_request(
    *,
    filename: str,
    file_size_bytes: int,
    status: str,
    text: str = "",
    duration_ms: float = 0,
    error: str = "",
    result: str = "",
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "filename": filename,
        "file_size_bytes": file_size_bytes,
        "status": status,
        "result": result or status,
        "text_preview": text[:200],
        "duration_ms": round(duration_ms, 2),
    }
    if error:
        entry["error"] = error

    _get_logger().info(json.dumps(entry, ensure_ascii=False))
