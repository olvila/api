#!/bin/bash
set -e

# ============================================================
# ASR 语音转文本服务 — Ubuntu 一键部署脚本
# 使用: sudo bash deploy.sh
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; exit 1; }

# ---------- 权限检查 ----------
[ "$(id -u)" -eq 0 ] || err "请用 sudo 运行: sudo bash deploy.sh"

# ---------- 收集配置 ----------
echo "============================================"
echo " ASR 服务部署脚本"
echo "============================================"
echo ""

read -p "请输入 NVIDIA API KEY: " NIM_API_KEY
[ -z "$NIM_API_KEY" ] && err "API KEY 不能为空"

read -p "请输入 MOI_KEYS (多个 key 用逗号分隔，留空跳过校验): " MOI_KEYS

read -p "是否部署 Nginx 反向代理? (y/n, demo 环境可选 n): " USE_NGINX

if [ "$USE_NGINX" = "y" ]; then
    read -p "请输入服务器域名或公网 IP: " SERVER_NAME
    [ -z "$SERVER_NAME" ] && err "域名/IP 不能为空"
fi

read -p "服务监听端口(默认 8008): " SERVER_PORT
SERVER_PORT=${SERVER_PORT:-8008}

read -p "文件大小限制(默认 30MB): " MAX_FILE_SIZE_MB
MAX_FILE_SIZE_MB=${MAX_FILE_SIZE_MB:-30}

read -p "请求超时秒数(默认 60): " REQUEST_TIMEOUT_SEC
REQUEST_TIMEOUT_SEC=${REQUEST_TIMEOUT_SEC:-60}

echo ""
log "开始部署..."

# ---------- 系统依赖 ----------
log "更新软件包..."
apt update -qq

if [ "$USE_NGINX" = "y" ]; then
    log "安装依赖 (python3, ffmpeg, nginx)..."
    apt install -y -qq python3 python3-pip python3-venv ffmpeg nginx
else
    log "安装依赖 (python3, ffmpeg)..."
    apt install -y -qq python3 python3-pip python3-venv ffmpeg
fi

# ---------- 项目部署 ----------
DEPLOY_DIR="/opt/asr-service"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

log "创建部署目录: ${DEPLOY_DIR}"
mkdir -p "${DEPLOY_DIR}"

log "复制项目文件..."
for item in app client docs tests requirements.txt; do
    rsync -a --exclude='__pycache__' --exclude='*.pyc' "${PROJECT_DIR}/${item}" "${DEPLOY_DIR}/" 2>/dev/null || \
    cp -r "${PROJECT_DIR}/${item}" "${DEPLOY_DIR}/"
done

# ---------- Python 虚拟环境 ----------
log "创建虚拟环境..."
python3 -m venv "${DEPLOY_DIR}/venv"

log "安装 Python 依赖..."
"${DEPLOY_DIR}/venv/bin/pip" install --upgrade pip -q
"${DEPLOY_DIR}/venv/bin/pip" install -r "${DEPLOY_DIR}/requirements.txt" -q

# ---------- 环境变量 ----------
log "写入环境变量..."
cat > "${DEPLOY_DIR}/asr.env" << EOF
NIM_API_KEY=${NIM_API_KEY}
MOI_KEYS=${MOI_KEYS}
MAX_FILE_SIZE_MB=${MAX_FILE_SIZE_MB}
REQUEST_TIMEOUT_SEC=${REQUEST_TIMEOUT_SEC}
EOF
chmod 600 "${DEPLOY_DIR}/asr.env"

# ---------- 日志目录 ----------
mkdir -p "${DEPLOY_DIR}/logs"

# ---------- systemd 服务 ----------
log "配置 systemd 服务..."
if [ "$USE_NGINX" = "y" ]; then
    chown -R www-data:www-data "${DEPLOY_DIR}"
    sed -e "s|/opt/asr-service|${DEPLOY_DIR}|g" -e "s|--port 8008|--port ${SERVER_PORT}|g" "${SCRIPT_DIR}/asr.service" > /etc/systemd/system/asr.service
else
    sed -e "s|/opt/asr-service|${DEPLOY_DIR}|g" -e "s|--port 8008|--port ${SERVER_PORT}|g" -e "s|User=www-data||" "${SCRIPT_DIR}/asr.service" > /etc/systemd/system/asr.service
fi

systemctl daemon-reload
systemctl enable asr
systemctl restart asr
sleep 2

# ---------- Nginx ----------
if [ "$USE_NGINX" = "y" ]; then
    log "配置 Nginx..."
    sed "s/SERVER_NAME_PLACEHOLDER/${SERVER_NAME}/g" "${SCRIPT_DIR}/nginx.conf" > /etc/nginx/sites-available/asr
    ln -sf /etc/nginx/sites-available/asr /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl reload nginx
fi

# ---------- 防火墙 ----------
log "配置防火墙..."
ufw --force enable 2>/dev/null || true
ufw allow 22/tcp 2>/dev/null || true
ufw allow "${SERVER_PORT}/tcp" 2>/dev/null || true
if [ "$USE_NGINX" = "y" ]; then
    ufw allow 80/tcp 2>/dev/null || true
    ufw allow 443/tcp 2>/dev/null || true
fi
ufw reload 2>/dev/null || true

# ---------- 验证 ----------
log "验证服务..."
sleep 1

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8008/health" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    echo ""
    echo "============================================"
    echo -e " ${GREEN}部署成功！${NC}"
    echo "============================================"
    echo " 健康检查: http://${SERVER_NAME}/health"
    echo " API 文档: http://${SERVER_NAME}/docs"
    echo " 日志查询: http://${SERVER_NAME}/v1/logs"
    echo ""
    echo " 转写接口:"
    echo "   curl -X POST http://${SERVER_NAME}/v1/audio/transcriptions \\"
    echo "     -H \"moi_key: YOUR_KEY\" \\"
    echo "     -F \"file=@test.wav\""
    echo ""
    echo " 查看日志: journalctl -u asr -f"
    echo " 重启服务: systemctl restart asr"
    echo "============================================"
else
    warn "服务健康检查失败 (HTTP ${HTTP_CODE})，查看日志:"
    echo "  journalctl -u asr -n 50"
    echo "  cat ${DEPLOY_DIR}/logs/asr.log"
fi
