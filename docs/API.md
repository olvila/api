# ASR 语音转文本 API 文档

## 基础信息

- Base URL: `http://localhost:8008`
- 协议: HTTP REST
- 单段超时: 60 秒（总耗时: 文件上传约 90s / URL 模式约 120s）
- Demo 限速: 约 30 次/分钟（NVIDIA 试用 Key 限制）

---

## 1. 健康检查

```
GET /health
```

**响应示例:**
```json
{"status": "ok"}
```

---

## 2. 查询日志

```
GET /v1/logs?page=1&size=20&start=2026-05-20 16:30&end=2026-05-20 17:30
```

**请求参数:**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | 页码，必须 ≥ 1 |
| `size` | int | 20 | 每页条数，必须 ≥ 1 |
| `start` | string | 无 | 起始时间: `YYYY-MM-DD` / `YYYY-MM-DD HH` / `YYYY-MM-DD HH:MM` |
| `end` | string | 无 | 结束时间: `YYYY-MM-DD` / `YYYY-MM-DD HH` / `YYYY-MM-DD HH:MM` |
| `moi_key` | string (Header) | 必填 | 身份校验 key |

**时间格式:** 支持多种精度（UTC），末尾可选带 ` UTC` 后缀：

| 格式 | 示例 | 含义 |
|------|------|------|
| `YYYY-MM-DD` | `2026-05-21` | 当天 00:00 |
| `YYYY-MM-DD HH` | `2026-05-21 16` | 当天 16:00（整点） |
| `YYYY-MM-DD HH:MM` | `2026-05-21 16:30` | 精确到分钟 |
| `YYYY-MM-DD HH:MM:SS` | `2026-05-21 16:30:00` | 精确到秒（兼容，实际按分钟存储） |

`start` / `end` 均为可选参数，可自由组合：

| 组合 | 含义 |
|------|------|
| 都不传 | 查询全部日志 |
| 只传 `start` | 该时间之后的所有记录 |
| 只传 `end` | 该时间之前的所有记录 |
| 都传 | 指定时间段内的记录 |

**调用示例:**

```bash
# 查询 5月21日 全部日志
curl "http://localhost:8008/v1/logs?start=2026-05-21&end=2026-05-22" \
  -H "moi_key: YOUR_KEY"

# 查询昨天下午 4:30 到 5:30
curl "http://localhost:8008/v1/logs?start=2026-05-20%2016:30&end=2026-05-20%2017:30" \
  -H "moi_key: YOUR_KEY"

# 查询今天所有日志
curl "http://localhost:8008/v1/logs?start=2026-05-21" \
  -H "moi_key: YOUR_KEY"

# 查询昨天上午之前的所有日志
curl "http://localhost:8008/v1/logs?end=2026-05-20%2012:00" \
  -H "moi_key: YOUR_KEY"
```

**响应示例:**
```json
{
  "total": 81,
  "page": 1,
  "size": 20,
  "entries": [
    {
      "timestamp": "2026-05-20 05:43 UTC",
      "filename": "test.wav",
      "file_size_bytes": 51196,
      "result": "success",
      "text_preview": "This is a format test.",
      "duration_ms": 121.81
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `timestamp` | 请求时间（精确到分钟，UTC）|
| `filename` | 上传的文件名 |
| `file_size_bytes` | 文件大小（字节）|
| `result` | success / error / timeout |
| `text_preview` | 转写文本前 200 字符 |
| `duration_ms` | 处理耗时（毫秒）|
| `error` | 错误信息（仅失败时）|

**错误响应:**

**page/size 不合法 (400):**
```json
{
  "status_code": 400,
  "result": "error",
  "text": "",
  "error": "page 和 size 必须 ≥ 1"
}
```

**时间格式错误 (400):**
```json
{
  "status_code": 400,
  "result": "error",
  "text": "",
  "error": "时间格式错误: '...'，支持格式: YYYY-MM-DD / YYYY-MM-DD HH:MM，如 2026-05-21 或 2026-05-21 16:30"
}
```

> 日志文件存储在 `logs/asr.log`，JSON lines 格式，每天凌晨轮转，保留 30 天。

---

## 3. 语音转文本

```
POST /v1/audio/transcriptions
Content-Type: multipart/form-data
```

**请求参数 (二选一):**

| 参数 | 类型 | 说明 |
|------|------|------|
| `file` | file | 上传音频文件，≤30MB |
| `url` | string | 音频文件公网 URL |
| `moi_key` | string (Header) | 身份校验 key，必填 |

**支持的音频格式:**

> 调用方无需关心格式转换，传任意格式即可，服务端自动处理。

| 分类 | 格式 | 扩展名 | 说明 |
|------|------|------|------|
| 原生支持 | WAV | .wav | Linear PCM, 魔数 `RIFF` |
| 原生支持 | OPUS | .opus | 魔数 `OggS` |
| 原生支持 | FLAC | .flac | 魔数 `fLaC` |
| 自动转码 | MP3 | .mp3 | MPEG Audio Layer 3 |
| 自动转码 | M4A / AAC | .m4a .aac .mp4 | Advanced Audio Coding |
| 自动转码 | OGG Vorbis | .ogg .oga | Ogg 容器 |
| 自动转码 | WMA | .wma | Windows Media Audio |
| 自动转码 | AC3 / E-AC3 | .ac3 .eac3 | Dolby Digital |
| 自动转码 | AIFF / AIFC | .aiff .aif .aifc | Apple 无损格式 |
| 自动转码 | ALAC | .m4a .caf | Apple Lossless |
| 自动转码 | AMR | .amr .3ga | 通话录音 (窄带/宽带) |
| 自动转码 | APE | .ape | Monkey's Audio 无损 |
| 自动转码 | WavPack | .wv | 混合无损格式 |
| 自动转码 | TTA | .tta | True Audio 无损 |
| 自动转码 | WMA Lossless | .wma | Windows Media Audio 无损 |
| 自动转码 | PCM/S16 | .pcm .s16 | Raw PCM 采样数据 |

其他 ffmpeg 支持的容器格式（AVI、MKV、MOV、WebM 等）同样可自动提取音频轨转码。

**处理流程:**

```
对方上传文件 → 魔数检测格式
               ├─ WAV/OPUS/FLAC → 直接送 NVIDIA whisper
               └─ 其他格式       → ffmpeg 转码为 WAV → 送 NVIDIA whisper
```

**响应:**

| 状态码 | result | 说明 |
|--------|--------|------|
| 200 | success | 转写成功 |
| 401 | error | moi_key 缺失或无效 |
| 429 | error | 请求过于频繁（每分钟最多 30 次） |
| 400 | error | 参数错误 / 文件为空 / 格式不支持 / file和url同时使用 / URL文件过大 |
| 504 | timeout | 请求超时 |
| 413 | error | 文件大小超限 |
| 500 | error | 服务内部错误 |

**成功 (200):**
```json
{
  "status_code": 200,
  "result": "success",
  "text": "你好 这是一个语音识别测试。"
}
```

**认证失败 — 缺失 (401):**
```json
{
  "detail": "缺少 moi_key"
}
```

**认证失败 — 无效 (401):**
```json
{
  "detail": "无效的 moi_key"
}
```

**请求过于频繁 (429):**
```json
{
  "detail": "请求过于频繁，每分钟最多 30 次"
}
```

**超时 (504):**
```json
{
  "status_code": 504,
  "result": "timeout",
  "text": "",
  "error": "请求超时"
}
```

**参数缺失 (400):**
```json
{
  "status_code": 400,
  "result": "error",
  "text": "",
  "error": "请提供 file (上传文件) 或 url (公网地址)"
}
```

**file 和 url 同时使用 (400):**
```json
{
  "status_code": 400,
  "result": "error",
  "text": "",
  "error": "file 和 url 不能同时使用，请二选一"
}
```

**文件为空 (400):**
```json
{
  "status_code": 400,
  "result": "error",
  "text": "",
  "error": "文件为空，请上传有效的音频文件"
}
```

**格式不支持 (400):**
```json
{
  "status_code": 400,
  "result": "error",
  "text": "",
  "error": "不支持的音频格式，无法转码"
}
```

**文件过大 — 上传 (413):**
```json
{
  "status_code": 413,
  "result": "error",
  "text": "",
  "error": "文件大小 31.0MB 超过限制 30MB"
}
```

**文件过大 — URL (400):**
```json
{
  "status_code": 400,
  "result": "error",
  "text": "",
  "error": "文件大小 31.0MB 超过限制 30MB"
}
```

**响应字段:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `status_code` | int | HTTP 状态码 |
| `result` | string | success / error / timeout |
| `text` | string | 转写文本（成功时） |
| `error` | string | 错误信息（失败时） |

---

## 4. 调用示例

### curl

**上传文件:**
```bash
curl -X POST http://localhost:8008/v1/audio/transcriptions \
  -H "moi_key: YOUR_KEY" \
  -F "file=@/path/to/audio.wav"
```

**公网 URL:**
```bash
curl -X POST http://localhost:8008/v1/audio/transcriptions \
  -H "moi_key: YOUR_KEY" \
  -F "url=https://example.com/audio.wav"
```

### Python

**上传文件字节流 (对方系统常用):**
```python
import requests

resp = requests.post(
    "http://你的服务器/v1/audio/transcriptions",
    files={"file": ("audio.mp3", file_bytes)},
    headers={"moi_key": "YOUR_KEY"},
    timeout=65,
)
print(resp.json())  # {"status_code":200, "result":"success", "text":"..."}
```

**公网 URL:**
```python
import requests

resp = requests.post(
    "http://你的服务器/v1/audio/transcriptions",
    data={"url": "https://对方系统.com/audio.mp3"},
    headers={"moi_key": "YOUR_KEY"},
    timeout=65,
)
print(resp.json()["text"])
```

---

## 附注

- 语言自动检测，中英文均可识别
- 返回的 `text` 字段包含自动标点
- 调用方无需关心音频格式，MP3/M4A 等非原生格式服务端自动转码
- 仅支持单次上传单个文件，不能同时使用 file 和 url
