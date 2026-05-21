# ASR 语音转文本服务 — 部署指南

## 项目简介

基于 NVIDIA NIM whisper-large-v3 的语音转文本 API 服务。

- 仓库: https://github.com/olvila/api
- API 文档: `/docs` (Swagger UI)
- 健康检查: `/health`
- 日志查询: `/v1/logs?page=1&size=20`

---

## 项目文件结构

```
api/
├── app/                           # 应用核心代码
│   ├── config.py                  # 环境变量读取
│   ├── logger.py                  # 日志记录 (JSON lines, 按天滚动)
│   ├── main.py                    # FastAPI 入口 + 3 个接口
│   └── nim_client.py              # NVIDIA NIM gRPC 客户端 + ffmpeg 转码
├── client/                        # 客户端集成示例
│   ├── client.py                  # 本地测试客户端 (接收文件路径)
│   └── client_for_third.py        # 第三方集成模板 (接收 bytes)
├── deploy/                        # 部署配置文件
│   ├── deploy.sh                  # Ubuntu 裸机一键部署脚本
│   ├── asr.service                # systemd 服务模板
│   ├── nginx.conf                 # 裸机 Nginx 配置模板 (sed 替换)
│   ├── nginx-docker.conf.template # Docker Nginx 配置模板 (envsubst 替换)
│   └── nginx-entrypoint.sh        # Docker Nginx 启动前置脚本
├── docs/
│   └── API.md                     # API 接口文档
├── tests/                         # 测试用例
│   ├── test_runner.py             # 20 个测试用例 (10 种音频格式)
│   ├── test_multi_file.py         # 多文件上传测试
│   └── test_audio.wav             # 测试用音频文件
├── logs/                          # 日志目录 (gitignore)
│   └── asr.log                    # 转写请求日志
├── Dockerfile                     # ASR 服务镜像
├── docker-compose.yml             # 容器编排 (asr + nginx)
├── .env.example                   # 环境变量模板
├── .env                           # 实际环境变量 (gitignore, 不入库)
├── .dockerignore                  # Docker 构建排除
├── .gitignore
└── requirements.txt               # Python 依赖
```

---

## 环境变量

`.env` 文件内容（`.env.example` 为模板）:

```ini
NIM_API_KEY=nvapi-你的KEY          # 必填，NVIDIA API Key
SERVER_NAME=你的域名或公网IP        # 必填，Nginx 绑定域名
MAX_FILE_SIZE_MB=30                # 可选，文件大小限制，默认 30
REQUEST_TIMEOUT_SEC=60             # 可选，单段超时秒数，默认 60
```

两个部署模式共用 `.env`，Docker 方式通过 `docker compose` 自动注入，裸机方式由 `deploy.sh` 交互输入。

---

## 日志存储

### 存储路径

| 部署模式 | ASR 日志路径 | Nginx 日志路径 |
|---------|-------------|---------------|
| Docker | 宿主机 `./logs/asr.log` (挂载自容器 `/app/logs`) | 宿主机 `./logs/nginx/` |
| 裸机 | `/opt/asr-service/logs/asr.log` | `/var/log/nginx/` |

### 日志格式

JSON lines，每条一行：

```json
{
  "timestamp": "2026-05-21 09:36 UTC",
  "filename": "test.wav",
  "file_size_bytes": 69118,
  "result": "success",
  "text_preview": "你好 这是一个语音识别测试。",
  "duration_ms": 1027.2
}
```

### 日志字段说明

| 字段 | 说明 |
|------|------|
| `timestamp` | 请求时间，精确到分钟，UTC |
| `filename` | 上传的文件名 |
| `file_size_bytes` | 文件大小（字节） |
| `result` | 结果类型: `success` / `error` / `timeout` |
| `text_preview` | 转写文本前 200 字符 |
| `duration_ms` | 处理耗时（毫秒） |
| `error` | 错误信息（仅失败时） |

### 日志轮转

- 每天凌晨自动切割，保留 30 天
- 通过 `/v1/logs?page=1&size=20` 接口远程查询

---

## 方式一：Docker 部署（推荐）

### 前置条件

1. 服务器已安装 Docker & Docker Compose
2. 开放 80/443 端口

### 部署步骤

```bash
# 1. 拉取代码
git clone https://github.com/olvila/api.git
cd api

# 2. 配置环境变量
cp .env.example .env
vim .env
```

**.env 填写示例:**

```ini
NIM_API_KEY=nvapi-KnLh0c2Dz_xxx
SERVER_NAME=asr.example.com
MAX_FILE_SIZE_MB=30
REQUEST_TIMEOUT_SEC=60
```

```bash
# 3. 启动
docker compose up -d

# 4. 验证
curl http://localhost/health
```

### 架构

```
客户端 :80 → Nginx 容器 → asr 容器 :8008 → grpc.nvcf.nvidia.com:443
                │                  │
                │              ./logs/asr.log (JSON lines)
                │
            ./logs/nginx/ (访问日志)
```

### docker-compose.yml 内容

```yaml
services:
  asr:
    build: .
    container_name: asr-service
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  nginx:
    image: nginx:stable-alpine
    container_name: asr-nginx
    ports:
      - "80:80"
      - "443:443"
    environment:
      - SERVER_NAME=${SERVER_NAME}
    volumes:
      - ./deploy/nginx-docker.conf.template:/etc/nginx/conf.d/default.conf.template:ro
      - ./deploy/nginx-entrypoint.sh:/docker-entrypoint.d/40-envsubst.sh:ro
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - asr
    restart: unless-stopped
```

### Dockerfile 内容

```dockerfile
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p logs && chown nobody logs

USER nobody

EXPOSE 8008

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
```

### 运维命令

```bash
# 查看应用日志
docker compose logs -f asr

# 查看 Nginx 日志
docker compose logs -f nginx

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 更新代码后重建
git pull
docker compose up -d --build
```

### 关键配置文件说明

| 文件 | 用途 |
|------|------|
| `Dockerfile` | asr 服务镜像构建 (python:3.13-slim + ffmpeg) |
| `docker-compose.yml` | 编排 asr + nginx 两个容器，挂载日志，注入环境变量 |
| `.env` | 环境变量，`docker compose` 自动读取，nginx 通过 `environment` 注入 `SERVER_NAME` |
| `deploy/nginx-docker.conf.template` | Nginx 配置模板，`${SERVER_NAME}` 占位 |
| `deploy/nginx-entrypoint.sh` | Nginx 启动前执行 `envsubst`，将模板渲染为最终配置 |
| `.dockerignore` | 构建镜像时排除 .env / logs / tests / deploy 等无关文件 |

---

## 方式二：Ubuntu 裸机部署

### 前置条件

1. 服务器: Ubuntu 20.04+
2. 开放 80/443 端口

### 部署步骤

```bash
# 1. 拉取代码
git clone https://github.com/olvila/api.git
cd api

# 2. 执行部署脚本
sudo bash deploy/deploy.sh
```

### 脚本交互提问

```
请输入 NVIDIA API KEY: nvapi-xxx
请输入服务器域名或公网 IP: asr.example.com
是否配置 SSL 证书? (y/n, 需已绑定域名): n
文件大小限制(默认 30MB): [回车默认]
请求超时秒数(默认 60): [回车默认]
```

### 脚本自动完成的步骤

| 步骤 | 操作 |
|------|------|
| 1 | `apt install` python3 / pip / ffmpeg / nginx / certbot |
| 2 | 创建部署目录 `/opt/asr-service` |
| 3 | 复制 `app/` `client/` `requirements.txt` 到部署目录 |
| 4 | `python3 -m venv venv` 创建虚拟环境，安装 pip 依赖 |
| 5 | 写入 `/opt/asr-service/asr.env`（权限 600） |
| 6 | 写入 `/etc/systemd/system/asr.service`，enable + start |
| 7 | 写入 `/etc/nginx/sites-available/asr`，reload |
| 8 | `ufw allow` 22/80/443 |
| 9 | 可选: `certbot --nginx` 配置 SSL |
| 10 | `curl /health` 验证 |

### 裸机部署目录结构

```
/opt/asr-service/
├── app/                # 应用代码
│   ├── config.py
│   ├── logger.py
│   ├── main.py
│   └── nim_client.py
├── client/             # 客户端示例
├── venv/               # Python 虚拟环境
├── logs/               # 转写日志
│   └── asr.log         # JSON lines, 每天滚动, 保留 30 天
├── requirements.txt
└── asr.env             # 环境变量 (权限 600)
```

### 运维命令

```bash
# 查看服务状态
systemctl status asr

# 查看应用日志
journalctl -u asr -f

# 查看转写日志
tail -f /opt/asr-service/logs/asr.log

# 重启服务
systemctl restart asr

# Nginx 重载
systemctl reload nginx
```

### 裸机关键配置文件

| 文件 | 用途 |
|------|------|
| `deploy/deploy.sh` | 交互式一键部署脚本 |
| `deploy/asr.service` | systemd 服务模板，通过 `EnvironmentFile` 加载 asr.env |
| `deploy/nginx.conf` | Nginx 配置模板，脚本用 `sed` 将 `SERVER_NAME_PLACEHOLDER` 替换为实际域名 |

**两种 Nginx 配置的区别：**

| | Docker | 裸机 |
|------|--------|------|
| 模板文件 | `deploy/nginx-docker.conf.template` | `deploy/nginx.conf` |
| 变量替换 | `envsubst` 注入 `${SERVER_NAME}` | `sed` 替换 `SERVER_NAME_PLACEHOLDER` |
| 代理目标 | `http://asr:8008` (Docker 内部网络) | `http://127.0.0.1:8008` |
| 日志路径 | `/var/log/nginx` (容器内) | `/var/log/nginx` (宿主机) |

---

## DNS 配置

在域名购买平台（阿里云/腾讯云/Cloudflare）添加 A 记录：

| 类型 | 主机记录 | 记录值 | TTL |
|------|---------|--------|-----|
| A | `@` | 服务器公网 IP | 600 |
| A | `*` | 服务器公网 IP | 600 |

- `@` → 根域名 `example.com`
- `*` → 泛解析，子域名通配 `api.example.com`

---

## 接口速查

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 `{"status":"ok"}` |
| `/v1/audio/transcriptions` | POST | 语音转文本 |
| `/v1/logs?page=1&size=20` | GET | 分页查询日志 |

**转写接口调用:**

```bash
# 上传文件
curl -X POST http://你的服务器/v1/audio/transcriptions \
  -F "file=@音频文件.wav"

# 公网 URL
curl -X POST http://你的服务器/v1/audio/transcriptions \
  -F "url=https://example.com/audio.mp3"
```

**响应:**

```json
// 成功
{"status_code": 200, "result": "success", "text": "识别文本"}

// 超时
{"status_code": 504, "result": "timeout", "error": "请求超时"}

// 不支持的格式
{"status_code": 400, "result": "error", "error": "不支持的音频格式，无法转码"}
```

### 支持的音频格式

| 分类 | 格式 |
|------|------|
| 原生支持 | WAV, OPUS, FLAC |
| 自动转码 | MP3, M4A, AAC, OGG, WMA, AC3, AIFF, ALAC, AMR, APE, WavPack, TTA |

---

## 超时说明

`REQUEST_TIMEOUT_SEC` 控制 NIM 调用单段超时，非请求总超时:

| 模式 | 步骤 | 最长耗时 |
|------|------|----------|
| 文件上传 | ffmpeg 转码(固定 30s) + gRPC 调用(60s) | 约 **90s** |
| URL 模式 | HTTP 下载(60s) + gRPC 调用(60s) | 约 **120s** |

---

## 故障排查

| 现象 | 检查 |
|------|------|
| 服务启动失败 | `docker compose logs asr` / `journalctl -u asr -n 50` |
| 健康检查不通 | `curl http://localhost:8008/health` 直接验证 asr 容器/进程 |
| Nginx 502 | asr 容器是否运行，Nginx 代理地址是否正确（Docker: `asr:8008`, 裸机: `127.0.0.1:8008`） |
| 上传非音频返回 400 | 预期行为，只支持音频格式 |
| 请求超时 | 检查 NIM_API_KEY 是否有效，服务器能否出站访问 `grpc.nvcf.nvidia.com:443` |
| 转写结果为空 | 查看转写日志 `logs/asr.log` 的 `text_preview` 和 `status` 字段 |
| gRPC 连接失败 | 服务器需能解析并连接 `grpc.nvcf.nvidia.com` (NVIDIA 云服务) |

```bash
# Docker 环境检查 gRPC 连通性
docker exec asr-service python3 -c "
import riva.client
auth = riva.client.Auth(use_ssl=True, uri='grpc.nvcf.nvidia.com:443',
    metadata_args=[('function-id','b702f636-f60c-4a3d-a6f4-f3568c13bd7d'),
                   ('authorization','Bearer YOUR_KEY')])
print('gRPC 连接正常')
"
```

---

## 客户端集成

详见 `client/client_for_third.py`，对方系统只需发一个 multipart/form-data POST 请求:

```python
import requests

resp = requests.post(
    "http://你的服务器/v1/audio/transcriptions",
    files={"file": ("文件名.mp3", file_bytes)},
    timeout=65,
)
print(resp.json()["text"])
```

任何语言均可集成（Java/Go/JS），本质就是一个带文件上传的 HTTP POST。
