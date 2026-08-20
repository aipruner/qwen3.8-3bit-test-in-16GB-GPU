#!/usr/bin/env bash
# Qwen3.8-27B on RTX 5070 Ti 16GB (WSL2) — llama-server launcher
# Usage: qwen38.sh [agent|long|safe|safe-ngram|vision|dflash|dflash-ngram|stop|status|logs|url]
set -euo pipefail

CONF="${QWEN38_CONF:-$HOME/.config/qwen38.env}"
[ -f "$CONF" ] && . "$CONF"

MODELS=${QWEN38_MODELS:-/home/kino/models/qwen3.8-27b}
IMAGE=${QWEN38_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda}
NAME=${QWEN38_NAME:-qwen38}
PORT=${QWEN38_PORT:-18038}
BIND=${QWEN38_BIND:-127.0.0.1}
MODEL=${QWEN38_MODEL:-Qwen3.8-27B-UD-Q3_K_XL.gguf}
DRAFT=${QWEN38_DRAFT:-Qwen3.8-27B-DFlash2-Q4_K_M.gguf}
APIKEY=${QWEN38_API_KEY:-}
PROFILE=${1:-agent}

# DFlash 2 needs llama.cpp PR #27342. Stock full-cuda only loads DFlash 1 GGUFs.
DFLASH_IMAGE=${QWEN38_DFLASH_IMAGE:-local/llama.cpp:dflash2-cuda}

# -ngl 99      all 64 layers on GPU. One CPU layer costs ~60% generation speed.
# -fa 1        flash attention
# --jinja      GGUF chat template (required for tool calling)
# --parallel 1 speculative decoding only pays off on a single in-flight request
COMMON=(-m "/models/${MODEL}" --host 0.0.0.0 --port 8080
        -ngl 99 -fa 1 --jinja --parallel 1 -t 20 --fit off
        --alias qwen3.8-27b)
[ -n "$APIKEY" ] && COMMON+=(--api-key "$APIKEY")

# Native MTP: nextn head is already inside the GGUF (blk.64.nextn.*).
MTP=(--spec-type draft-mtp --spec-draft-n-max 4)

# ngram-mod (llama.cpp PR #19164): hash recent token n-grams and replay the
# continuation when the same n-gram reappears. Table is ~16 MiB RAM, not VRAM.
# Helps repeated JSON / tool-call shapes; unique prose gets almost no boost.
# Same lookup sizes as the Reddit recipe. n_match=32 (llama.cpp warns if < 16).
# safe-ngram: 24K MTP + ngram, DFlash 2 image so the build matches dflash-ngram.
# dflash-ngram: 16K q4_0. 8K q8_0 + ngram spilled when idle VRAM was ~700 MiB.
NGRAM=(--spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32)
MTP_NGRAM=(--spec-type draft-mtp,ngram-mod --spec-draft-n-max 4 "${NGRAM[@]}")

# DFlash 2: extra ~1.1 GiB draft GGUF. On UD-Q3_K_XL the Reddit 105k/q5_1/n-max 5
# recipe spills on this 16GB card. Measured working point: 8K, q8_0, n-max 4,
# batch 256 (see harness/results/dflash2/fit-gpu2.log).
DFLASH=(--spec-type draft-dflash --spec-draft-n-max 4
        --spec-draft-model "/models/${DRAFT}" --n-gpu-layers-draft 99
        -b 256 -ub 128)
DFLASH_NGRAM=(--spec-type draft-dflash,ngram-mod --spec-draft-n-max 3
        --spec-draft-model "/models/${DRAFT}" --n-gpu-layers-draft 99
        -b 256 -ub 128
        "${NGRAM[@]}")

case "$PROFILE" in
  agent)  ARGS=("${COMMON[@]}" -c 32768 -ctk q8_0 -ctv q8_0 "${MTP[@]}"); NEED=13300 ;;
  long)   ARGS=("${COMMON[@]}" -c 32768 -ctk q4_0 -ctv q4_0 "${MTP[@]}"); NEED=13300 ;;
  safe)   ARGS=("${COMMON[@]}" -c 24576 -ctk q8_0 -ctv q8_0 "${MTP[@]}"); NEED=13300 ;;
  safe-ngram) ARGS=("${COMMON[@]}" -c 24576 -ctk q8_0 -ctv q8_0 "${MTP_NGRAM[@]}"); NEED=13300; IMAGE=$DFLASH_IMAGE ;;
  vision) ARGS=("${COMMON[@]}" -c 16384 -ctk q8_0 -ctv q8_0 --mmproj /models/mmproj-F16.gguf); NEED=13300 ;;
  dflash) ARGS=("${COMMON[@]}" -c 8192 -ctk q8_0 -ctv q8_0 "${DFLASH[@]}"); NEED=14000; IMAGE=$DFLASH_IMAGE ;;
  dflash-ngram) ARGS=("${COMMON[@]}" -c 8192 -ctk q4_0 -ctv q4_0 "${DFLASH_NGRAM[@]}"); NEED=14000; IMAGE=$DFLASH_IMAGE ;;
  stop)   docker rm -f "$NAME" >/dev/null 2>&1 && echo "stopped" || echo "not running"; exit 0 ;;
  status)
    docker ps --filter "name=^${NAME}$" --format 'container: {{.Names}}  {{.Status}}  {{.Ports}}'
    nvidia-smi --query-gpu=memory.used,memory.free --format=csv
    echo "endpoint: http://${BIND}:${PORT}/v1   (config: ${CONF})"
    curl -s -m 3 "http://127.0.0.1:${PORT}/health" 2>/dev/null && echo || echo "health: unreachable"
    exit 0 ;;
  logs)   docker logs -f "$NAME"; exit 0 ;;
  url)    echo "http://${BIND}:${PORT}/v1"; exit 0 ;;
  *) echo "unknown profile: $PROFILE  (agent|long|safe|safe-ngram|vision|dflash|dflash-ngram|stop|status|logs|url)"; exit 1 ;;
esac

# Stop our own container first so the free-VRAM reading is real.
docker rm -f "$NAME" >/dev/null 2>&1 || true
sleep 2

FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
if [ "$FREE" -lt "$NEED" ]; then
  echo "⚠️  free VRAM = ${FREE} MiB < ${NEED} MiB。"
  echo "   模型會溢出到 shared memory，生成速度會從 ~110 tokens/秒掉到個位數。"
  echo "   先關掉吃 VRAM 的程式，或改用: $0 safe"
  nvidia-smi --query-compute-apps=pid,used_memory,name --format=csv
  if [ "${QWEN38_FORCE:-}" = 1 ]; then
    echo "QWEN38_FORCE=1, continuing"
  elif [ -t 0 ]; then
    read -rp "   仍要繼續？[y/N] " a; [ "$a" = y ] || exit 1
  else
    echo "non-interactive stdin: abort (set QWEN38_FORCE=1 to override)"
    exit 1
  fi
fi

docker run -d --restart unless-stopped --name "$NAME" --gpus all \
  -p "${BIND}:${PORT}:8080" -v "${MODELS}:/models" \
  --entrypoint /app/llama-server "$IMAGE" "${ARGS[@]}" >/dev/null

echo "profile: ${PROFILE}   model: ${MODEL}"
case "$PROFILE" in dflash*) echo "draft:   ${DRAFT}" ;; esac
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
