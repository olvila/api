# ASR 语音转文本 API 文档

## 基础信息

- Base URL: `http://localhost:8008`
- 协议: HTTP REST
- 超时: 60 秒

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
GET /v1/logs?page=1&size=20
```

**请求参数:**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | 页码 |
| `size` | int | 20 | 每页条数 |

**响应示例:**
```json
{
  "total": 81,
  "page": 1,
  "size": 20,
  "entries": [
    {
      "timestamp": "2026-05-20 05:43:52 UTC",
      "filename": "test.wav",
      "file_size_bytes": 51196,
      "status": "success",
      "text_preview": "This is a format test.",
      "duration_ms": 121.81
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `timestamp` | 请求时间（精确到秒，UTC）|
| `filename` | 上传的文件名 |
| `file_size_bytes` | 文件大小（字节）|
| `status` | success / error / empty |
| `text_preview` | 转写文本前 200 字符 |
| `duration_ms` | 处理耗时（毫秒）|
| `error` | 错误信息（仅失败时）|

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

其他 ffmpeg 支持的音频/视频格式（如 AVI、MKV、MOV、WebM 等容器中的音频轨）同样支持自动转码。

**处理流程:**

```
对方上传文件 → 魔数检测格式
               ├─ WAV/OPUS/FLAC → 直接送 NVIDIA whisper
               └─ 其他格式       → ffmpeg 转码为 WAV → 送 NVIDIA whisper
```

**成功响应 (200):**
```json
{
  "status_code": 200,
  "result": "success",
  "text": "你好 这是一个语音识别测试。"
}
```

**错误响应 (400):**
```json
{
  "status_code": 400,
  "result": "error",
  "text": "",
  "error": "请提供 file (上传文件) 或 url (公网地址)"
}
```

**文件过大 (413):**
```json
{
  "status_code": 413,
  "result": "error",
  "text": "",
  "error": "文件大小 31.0MB 超过限制 30MB"
}
```

---

## 3. 调用示例

### curl

**上传文件:**
```bash
curl -X POST http://localhost:8008/v1/audio/transcriptions \
  -F "file=@/path/to/audio.wav"
```

**公网 URL:**
```bash
curl -X POST http://localhost:8008/v1/audio/transcriptions \
  -F "url=https://example.com/audio.wav"
```

### Python (第三方系统集成)

**方式一：本地文件路径:**
```python
import requests

with open("audio.wav", "rb") as f:
    resp = requests.post(
        "http://localhost:8008/v1/audio/transcriptions",
        files={"file": f},
        timeout=65,
    )
print(resp.json())  # {"status_code":200, "result":"success", "text":"..."}
```

**方式二：内存字节流 (对方系统常用):**
```python
import requests

# file_bytes 来自对方框架的上传处理
# Django  : request.FILES['audio'].read()
# Flask   : request.files['audio'].read()
# FastAPI : await file.read()

filename = "用户上传的音频.mp3"
resp = requests.post(
    "http://你的服务器IP:8008/v1/audio/transcriptions",
    files={"file": (filename, file_bytes)},
    timeout=65,
)
result = resp.json()
print(result["text"])  # 转写文本
```

**方式三：公网 URL:**
```python
import requests

resp = requests.post(
    "http://localhost:8008/v1/audio/transcriptions",
    data={"url": "https://对方系统.com/audio.mp3"},
    timeout=65,
)
print(resp.json()["text"])
```

### 响应说明

**成功:**
```json
{
    "status_code": 200,
    "result": "success",
    "text": "你好 这是一个语音识别测试。"
}
```

**失败:**
```json
{
    "status_code": 400,
    "result": "error",
    "text": "",
    "error": "请提供 file (上传文件) 或 url (公网地址)"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status_code` | int | HTTP 状态码 |
| `result` | string | `success` 或 `error` |
| `text` | string | 转写文本 (成功时) |
| `error` | string | 错误信息 (失败时) |

---

## 附注

- Demo 阶段限速：约 30 次/分钟（NVIDIA 试用 Key 限制）
- 返回的 `text` 字段包含自动标点
- 语言自动检测，英文为主，中文也可识别
- 调用方无需关心音频格式，MP3/M4A 等格式服务端自动转码
