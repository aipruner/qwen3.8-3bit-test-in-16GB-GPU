#!/usr/bin/env bash
# Try to fit Qwen3.8-27B-IQ4_XS on this card. $1=ctx  $2=kv type  $3=name
set -u
CTX=${1:-32768}; KV=${2:-q8_0}; TAG=${3:-t}
docker rm -f qwen38 >/dev/null 2>&1 || true
sleep 2
FREE0=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
docker run -d --name qwen38 --gpus all -p 127.0.0.1:18038:8080 \
  -v /home/kino/models/qwen3.8-27b:/models \
  --entrypoint /app/llama-server ghcr.io/ggml-org/llama.cpp:full-cuda \
  -m /models/Qwen3.8-27B-IQ4_XS.gguf --host 0.0.0.0 --port 8080 \
  -ngl 99 -fa 1 --jinja --parallel 1 -t 20 --alias qwen3.8-27b \
  -c "$CTX" -ctk "$KV" -ctv "$KV" \
  --spec-type draft-mtp --spec-draft-n-max 4 >/dev/null
for i in $(seq 1 300); do
  curl -s -m 2 http://127.0.0.1:18038/health 2>/dev/null | grep -q '"ok"' && break
  docker ps --format '{{.Names}}' | grep -q '^qwen38$' || { echo "LOAD FAILED ctx=$CTX kv=$KV"; docker logs qwen38 2>&1 | tail -12; exit 1; }
  sleep 1
done
FREE1=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
echo "ctx=$CTX kv=$KV  free_before=${FREE0}MiB  free_after=${FREE1}MiB  used=$((FREE0-FREE1))MiB"
