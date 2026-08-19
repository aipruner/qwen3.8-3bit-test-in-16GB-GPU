#!/usr/bin/env bash
# Qwen3.8-27B on RTX 5070 Ti 16GB (WSL2) — llama-server launcher
# 用法: qwen38.sh [agent|long|safe|vision|stop|status|logs|url]
set -euo pipefail

# ── 設定（優先序：環境變數 > ~/.config/qwen38.env > 這裡的預設值）────────
CONF="${QWEN38_CONF:-$HOME/.config/qwen38.env}"
[ -f "$CONF" ] && . "$CONF"

MODELS=${QWEN38_MODELS:-/home/kino/models/qwen3.8-27b}
IMAGE=${QWEN38_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda}
NAME=${QWEN38_NAME:-qwen38}
PORT=${QWEN38_PORT:-8088}             # 對外 port
BIND=${QWEN38_BIND:-127.0.0.1}        # 綁定介面。改成 0.0.0.0 才能被區網其他機器連到
MODEL=${QWEN38_MODEL:-Qwen3.8-27B-UD-Q3_K_XL.gguf}  # 12.51 GiB — 唯一能全常駐 16GB VRAM 的檔
APIKEY=${QWEN38_API_KEY:-}            # 設了就要求 Authorization: Bearer <key>
PROFILE=${1:-agent}

# ── 共用參數 ────────────────────────────────────────────────────────────
# -ngl 99      全部 64 層上 GPU。這個架構只要有 1 層落在 CPU，tg 就掉 60%（實測）
# -fa 1        flash attention
# --jinja      使用 GGUF 內建 chat template（tool calling 需要）
# --parallel 1 MTP speculative decoding 只在單一 request 下有效益
COMMON=(-m "/models/${MODEL}" --host 0.0.0.0 --port 8080
        -ngl 99 -fa 1 --jinja --parallel 1 -t 20
        --alias qwen3.8-27b)
[ -n "$APIKEY" ] && COMMON+=(--api-key "$APIKEY")
# MTP: 模型內嵌 nextn head（blk.64.nextn.*），不需要額外 draft model
MTP=(--spec-type draft-mtp --spec-draft-n-max 4)

case "$PROFILE" in
  # 預設：coding agent / 工具呼叫。q8_0 KV 保護 long-context 下的 tool-call 可靠度
  agent)  ARGS=("${COMMON[@]}" -c 32768 -ctk q8_0 -ctv q8_0 "${MTP[@]}") ;;
  # 更長 context：q4_0 KV 把每 token 成本壓到 16KB。速度幾乎相同，但 KV 精度較低
  long)   ARGS=("${COMMON[@]}" -c 32768 -ctk q4_0 -ctv q4_0 "${MTP[@]}") ;;
  # VRAM 吃緊時（Windows 桌面/其他程式佔用變多）用這個，headroom 最大
  safe)   ARGS=("${COMMON[@]}" -c 24576 -ctk q8_0 -ctv q8_0 "${MTP[@]}") ;;
  # 圖片/影片理解。注意：llama.cpp 目前 mmproj 與 MTP 不能並用，所以這個 profile 慢很多
  vision) ARGS=("${COMMON[@]}" -c 16384 -ctk q8_0 -ctv q8_0 --mmproj /models/mmproj-F16.gguf) ;;
  stop)   docker rm -f "$NAME" >/dev/null 2>&1 && echo "stopped" || echo "not running"; exit 0 ;;
  status)
    docker ps --filter "name=^${NAME}$" --format 'container: {{.Names}}  {{.Status}}  {{.Ports}}'
    nvidia-smi --query-gpu=memory.used,memory.free --format=csv
    echo "endpoint: http://${BIND}:${PORT}/v1   (config: ${CONF})"
    curl -s -m 3 "http://127.0.0.1:${PORT}/health" 2>/dev/null && echo || echo "health: unreachable"
    exit 0 ;;
  logs)   docker logs -f "$NAME"; exit 0 ;;
  url)    echo "http://${BIND}:${PORT}/v1"; exit 0 ;;
  *) echo "unknown profile: $PROFILE  (agent|long|safe|vision|stop|status|logs|url)"; exit 1 ;;
esac

# ── VRAM 預檢 ───────────────────────────────────────────────────────────
FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
NEED=13300
if [ "$FREE" -lt "$NEED" ]; then
  echo "⚠️  free VRAM = ${FREE} MiB < ${NEED} MiB。"
  echo "   模型會溢出到 shared memory，tg 會從 ~110 t/s 掉到個位數。"
  echo "   先關掉吃 VRAM 的程式（瀏覽器硬體加速、遊戲、其他推論服務），或改用: $0 safe"
  nvidia-smi --query-compute-apps=pid,used_memory,name --format=csv
  read -rp "   仍要繼續？[y/N] " a; [ "$a" = y ] || exit 1
fi

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --restart unless-stopped --name "$NAME" --gpus all \
  -p "${BIND}:${PORT}:8080" -v "${MODELS}:/models" \
  --entrypoint /app/llama-server "$IMAGE" "${ARGS[@]}" >/dev/null

echo "profile: ${PROFILE}   model: ${MODEL}"
printf 'waiting for model load'
for i in $(seq 1 240); do
  if curl -s -m 2 "http://127.0.0.1:${PORT}/health" 2>/dev/null | grep -q '"ok"'; then
    echo; echo "✅ ready → http://${BIND}:${PORT}/v1  (OpenAI-compatible)"
    echo "   Web UI  → http://${BIND}:${PORT}"
    [ -n "$APIKEY" ] && echo "   API key required (Authorization: Bearer ...)"
    nvidia-smi --query-gpu=memory.used,memory.free --format=csv
    exit 0
  fi
  docker ps --format '{{.Names}}' | grep -q "^${NAME}$" || { echo; echo "❌ 啟動失敗:"; docker logs "$NAME" 2>&1 | tail -20; exit 1; }
  printf '.'; sleep 1
done
echo; echo "❌ timeout"; docker logs "$NAME" 2>&1 | tail -20; exit 1
