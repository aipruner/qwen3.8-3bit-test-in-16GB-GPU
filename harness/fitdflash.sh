#!/usr/bin/env bash
# VRAM + 32-token probe for DFlash2 / MTP configs on this 16GB card.
# Health = generation speed > 60 tokens/sec. WSL2 will not OOM; it just crawls.
#
# Usage:
#   ./harness/fitdflash.sh              # run the default matrix
#   ./harness/fitdflash.sh one <tag>    # rerun one named row (see MATRIX below)
set -u
cd "$(dirname "$0")/.."
OUT="${FIT_OUT:-harness/results/dflash2}"
mkdir -p "$OUT"
LOG="$OUT/fit.log"
PORT=${QWEN38_PORT:-18038}
IMAGE=${QWEN38_IMAGE:-ghcr.io/ggml-org/llama.cpp:full-cuda}
DFLASH_IMAGE=${QWEN38_DFLASH_IMAGE:-local/llama.cpp:dflash2-cuda}
MODELS=${QWEN38_MODELS:-/home/kino/models/qwen3.8-27b}
TARGET=${QWEN38_MODEL:-Qwen3.8-27B-UD-Q3_K_XL.gguf}
DRAFT=${QWEN38_DRAFT:-Qwen3.8-27B-DFlash2-Q4_K_M.gguf}

# tag | spec | nmax | ctx | kv
MATRIX=$(cat <<'EOF'
d5-16k-q51      draft-dflash              5  16384  q5_1
d5-16k-q80      draft-dflash              5  16384  q8_0
d7-16k-q51      draft-dflash              7  16384  q5_1
d5-24k-q51      draft-dflash              5  24576  q5_1
d5-24k-q41      draft-dflash              5  24576  q4_1
d5-32k-q41      draft-dflash              5  32768  q4_1
d5ng-16k-q51    draft-dflash,ngram-mod     5  16384  q5_1
mtp4-16k-q51    draft-mtp                  4  16384  q5_1
mtp4-24k-q80    draft-mtp                  4  24576  q8_0
EOF
)

NGRAM=(--spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32)

probe_one() {
  local tag=$1 spec=$2 nmax=$3 ctx=$4 kv=$5
  echo "── $tag  spec=$spec n-max=$nmax ctx=$ctx kv=$kv"
  docker rm -f qwen38 >/dev/null 2>&1 || true
  sleep 2
  local free0
  free0=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)

  local args=(
    -m "/models/$TARGET" --host 0.0.0.0 --port 8080
    -ngl 99 -fa 1 --jinja --parallel 1 -t 20 --alias qwen3.8-27b --fit off
    -c "$ctx" -ctk "$kv" -ctv "$kv"
    --spec-type "$spec" --spec-draft-n-max "$nmax"
  )
  case "$spec" in
    *dflash*)
      args+=(--spec-draft-model "/models/$DRAFT" --n-gpu-layers-draft 99)
      ;;
  esac
  case "$spec" in
    *ngram-mod*) args+=("${NGRAM[@]}") ;;
  esac

  local img=$IMAGE
  case "$spec" in
    *dflash*) img=$DFLASH_IMAGE ;;
  esac

  docker run -d --name qwen38 --gpus all -p "127.0.0.1:${PORT}:8080" \
    -v "${MODELS}:/models" \
    --entrypoint /app/llama-server "$img" "${args[@]}" >/dev/null

  local ok=0
  for _ in $(seq 1 240); do
    if curl -s -m 2 "http://127.0.0.1:${PORT}/health" 2>/dev/null | grep -q '"ok"'; then
      ok=1; break
    fi
    docker ps --format '{{.Names}}' | grep -q '^qwen38$' || break
    sleep 1
  done
  if [ "$ok" != 1 ]; then
    printf "%-16s LOAD_FAILED\n" "$tag" | tee -a "$LOG"
    docker logs qwen38 2>&1 | tail -16 | tee -a "$LOG"
    return 1
  fi

  local free1 used
  free1=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
  used=$((free0 - free1))

  local result
  result=$(python3 - "$PORT" <<'PY'
import json, sys, requests
port = sys.argv[1]
try:
    r = requests.post(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        json={"model": "qwen3.8-27b",
              "messages": [{"role": "user", "content": "Say OK."}],
              "temperature": 0.7, "top_p": 0.8,
              "max_tokens": 32, "reasoning_effort": "low"},
        timeout=190).json()
except Exception as e:
    print(json.dumps({"err": str(e)}))
    sys.exit(0)
t = r.get("timings") or {}
u = r.get("usage") or {}
print(json.dumps({
    "gen": round(float(t.get("predicted_per_second") or 0), 1),
    "read": round(float(t.get("prompt_per_second") or 0), 1),
    "out": u.get("completion_tokens", 0),
    "timings": t,
}))
PY
)
  echo "{\"tag\":\"$tag\",\"spec\":\"$spec\",\"nmax\":$nmax,\"ctx\":$ctx,\"kv\":\"$kv\",\"used_mib\":$used,\"free_mib\":$free1,\"probe\":$result}" >> "$OUT/fit-raw.jsonl"
  python3 -c '
import json, sys
tag, spec, nmax, ctx, kv, used, free1, raw = sys.argv[1:]
d = json.loads(raw)
gen = float(d.get("gen") or 0)
verdict = "FITS" if gen > 60 else ("SPILLED" if gen > 0 else "NO_RESPONSE")
line = (f"{tag:<16} spec={spec:<28} n={nmax} ctx={ctx:<6} kv={kv:<4}  "
        f"used={used:>5} MiB  free={free1:>4} MiB  gen={gen:>6} tok/s  {verdict}")
print(line)
' "$tag" "$spec" "$nmax" "$ctx" "$kv" "$used" "$free1" "$result" | tee -a "$LOG"
}

run_matrix() {
  local only=${1:-}
  echo "# fitdflash $(date -Iseconds)  target=$TARGET  draft=$DRAFT" | tee "$LOG"
  echo "$MATRIX" | while read -r tag spec nmax ctx kv; do
    [ -z "$tag" ] && continue
    [ -n "$only" ] && [ "$tag" != "$only" ] && continue
    probe_one "$tag" "$spec" "$nmax" "$ctx" "$kv" || true
  done
}

case "${1:-all}" in
  all) run_matrix ;;
  one) run_matrix "${2:?tag}" ;;
  *) echo "usage: $0 [all|one <tag>]"; exit 1 ;;
esac
