#!/usr/bin/env bash
# 掃某個量化檔在這張卡上能開多長的 context。
# 用法: fit.sh <gguf檔名> <ctx> <kv型別>
# 健康 = 生成速度 > 60 tokens/秒；溢出 = 個位數
set -u
M=$1; CTX=$2; KV=$3
docker rm -f qwen38 >/dev/null 2>&1 || true
sleep 3
FREE0=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
docker run -d --name qwen38 --gpus all -p 127.0.0.1:8088:8080 \
  -v /home/kino/models/qwen3.8-27b:/models \
  --entrypoint /app/llama-server ghcr.io/ggml-org/llama.cpp:full-cuda \
  -m "/models/$M" --host 0.0.0.0 --port 8080 \
  -ngl 99 -fa 1 --jinja --parallel 1 -t 20 --alias qwen3.8-27b \
  -c "$CTX" -ctk "$KV" -ctv "$KV" \
  --spec-type draft-mtp --spec-draft-n-max 4 >/dev/null 2>&1
for i in $(seq 1 400); do
  curl -s -m 2 http://127.0.0.1:8088/health 2>/dev/null | grep -q '"ok"' && break
  docker ps --format '{{.Names}}' | grep -q '^qwen38$' || { echo "$M ctx=$CTX kv=$KV -> LOAD_FAILED"; docker logs qwen38 2>&1 | tail -6; exit 1; }
  sleep 1
done
FREE1=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
R=$(python3 - <<'PY'
import requests,json
r=requests.post("http://127.0.0.1:8088/v1/chat/completions",json={"model":"qwen3.8-27b",
  "messages":[{"role":"user","content":"Write a Python function to compute the nth Fibonacci number iteratively. Code only."}],
  "temperature":0.7,"top_p":0.8,"max_tokens":200,"reasoning_effort":"low"},timeout=1800).json()
t=r.get("timings",{}) or {}
print("%.1f %.0f"%(t.get("predicted_per_second",0),t.get("prompt_per_second",0)))
PY
)
GEN=$(echo $R | cut -d' ' -f1); RD=$(echo $R | cut -d' ' -f2)
VERDICT=$(python3 -c "print('FITS' if $GEN>60 else 'SPILLED')")
printf "%-32s ctx=%-6s kv=%-5s  used=%5s MiB  free_after=%4s MiB  gen=%6s tok/s  read=%6s tok/s  %s\n" \
  "$M" "$CTX" "$KV" "$((FREE0-FREE1))" "$FREE1" "$GEN" "$RD" "$VERDICT"
