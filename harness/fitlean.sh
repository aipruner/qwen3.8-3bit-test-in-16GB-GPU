#!/usr/bin/env bash
# 精簡版 fit 測試：量載入後的 VRAM 佔用 + 32 token 探針
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
  docker ps --format '{{.Names}}' | grep -q '^qwen38$' || { printf "%-30s ctx=%-6s kv=%-5s  LOAD_FAILED\n" "$M" "$CTX" "$KV"; docker logs qwen38 2>&1 | tail -4; exit 1; }
  sleep 1
done
FREE1=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
R=$(timeout 200 python3 -c "
import requests
try:
    r=requests.post('http://127.0.0.1:8088/v1/chat/completions',json={'model':'qwen3.8-27b',
      'messages':[{'role':'user','content':'Say OK.'}],'temperature':0.7,'top_p':0.8,
      'max_tokens':32,'reasoning_effort':'low'},timeout=190).json()
    t=r.get('timings',{}) or {}
    print('%.1f'%t.get('predicted_per_second',0))
except Exception: print('0.0')
")
V=$(python3 -c "print('FITS' if $R>60 else ('SPILLED' if $R>0 else 'NO_RESPONSE_IN_200s'))")
printf "%-30s ctx=%-6s kv=%-5s  used=%5s MiB  free=%4s MiB  gen=%6s tok/s  %s\n" \
  "$M" "$CTX" "$KV" "$((FREE0-FREE1))" "$FREE1" "$R" "$V"
