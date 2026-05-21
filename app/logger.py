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


def _parse_ts(ts: str) -> datetime:
    ts = ts.removesuffix(" UTC").strip()
    if len(ts) == 19 and ts[16] == ":":
        ts = ts[:16]  # 兼容旧格式 HH:MM:SS → HH:MM
    if len(ts) == 10:
        ts += " 00:00"  # 仅日期 → 当天 00:00
    elif len(ts) == 13:
        ts += ":00"     # 日期+小时 → 整点
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(
            f"时间格式错误: '{ts}'，支持格式: YYYY-MM-DD / YYYY-MM-DD HH:MM，如 2026-05-21 或 2026-05-21 16:30"
        ) from None


def query_logs(
    page: int = 1,
    size: int = 20,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """查询历史请求日志，支持分页和时间范围过滤"""
    log_files = sorted(LOG_DIR.glob("asr.log*"), reverse=True)
    entries: list[dict] = []

    t_start = _parse_ts(start) if start else datetime.min.replace(tzinfo=timezone.utc)
    t_end = _parse_ts(end) if end else datetime.max.replace(tzinfo=timezone.utc)

    for f in log_files:
        if f.exists():
            for line in f.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = entry.get("timestamp", "")
                if ts and t_start <= _parse_ts(ts) <= t_end:
                    entries.append(entry)

    entries.reverse()  # 最新的在前

    total = len(entries)
    idx_start = (page - 1) * size
    idx_end = idx_start + size
    page_entries = entries[idx_start:idx_end]

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
    result: str,
    text: str = "",
    duration_ms: float = 0,
    error: str = "",
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "filename": filename,
        "file_size_bytes": file_size_bytes,
        "result": result,
        "text_preview": text[:200],
        "duration_ms": round(duration_ms, 2),
    }
    if error:
        entry["error"] = error

    _get_logger().info(json.dumps(entry, ensure_ascii=False))
