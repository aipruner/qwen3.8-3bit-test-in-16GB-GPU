#!/usr/bin/env bash
# Max-context fit for ngram-mod stacked on MTP vs DFlash 2.
# Same llama.cpp image (dflash2-cuda) for both. Health = gen > 60 tok/s.
#
# Usage:
#   ./harness/fitngram.sh
#   ./harness/fitngram.sh one mtp-ng-24k-q80
set -u
cd "$(dirname "$0")/.."
OUT="${FIT_OUT:-harness/results/ngram}"
mkdir -p "$OUT"
LOG="$OUT/fit.log"
PORT=${QWEN38_PORT:-18038}
IMAGE=${QWEN38_DFLASH_IMAGE:-local/llama.cpp:dflash2-cuda}
MODELS=${QWEN38_MODELS:-/home/kino/models/qwen3.8-27b}
TARGET=${QWEN38_MODEL:-Qwen3.8-27B-UD-Q3_K_XL.gguf}
DRAFT=${QWEN38_DRAFT:-Qwen3.8-27B-DFlash2-Q4_K_M.gguf}

# tag | spec | nmax | ctx | kv | extra batch flags as "-" or "b256"
MATRIX=$(cat <<'EOF'
mtp-ng-8k-q80    draft-mtp,ngram-mod     4  8192   q8_0  -
mtp-ng-16k-q80   draft-mtp,ngram-mod     4  16384  q8_0  -
mtp-ng-24k-q80   draft-mtp,ngram-mod     4  24576  q8_0  -
mtp-ng-32k-q80   draft-mtp,ngram-mod     4  32768  q8_0  -
df-ng-8k-q80     draft-dflash,ngram-mod  4  8192   q8_0  b256
df-ng-12k-q80    draft-dflash,ngram-mod  4  12288  q8_0  b256
df-ng-16k-q80    draft-dflash,ngram-mod  4  16384  q8_0  b256
df-ng-16k-q40    draft-dflash,ngram-mod  4  16384  q4_0  b256
df-ng-24k-q40    draft-dflash,ngram-mod  4  24576  q4_0  b256
EOF
)

NGRAM=(--spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32)

probe_one() {
  local tag=$1 spec=$2 nmax=$3 ctx=$4 kv=$5 batch=$6
  echo "── $tag  spec=$spec n-max=$nmax ctx=$ctx kv=$kv batch=$batch"
  docker rm -f qwen38 >/dev/null 2>&1 || true
  sleep 2

  local args=(
    -m "/models/$TARGET" --host 0.0.0.0 --port 8080
    -ngl 99 -fa 1 --jinja --parallel 1 -t 20 --alias qwen3.8-27b --fit off
    -c "$ctx" -ctk "$kv" -ctv "$kv"
    --spec-type "$spec" --spec-draft-n-max "$nmax"
    "${NGRAM[@]}"
  )
  case "$spec" in
    *dflash*)
      args+=(--spec-draft-model "/models/$DRAFT" --n-gpu-layers-draft 99)
      ;;
  esac
  if [ "$batch" = b256 ]; then
    args+=(-b 256 -ub 128)
  fi

  docker run -d --name qwen38 --gpus all -p "127.0.0.1:${PORT}:8080" \
    -v "${MODELS}:/models" \
    --entrypoint /app/llama-server "$IMAGE" "${args[@]}" >/dev/null

  local ok=0
  for _ in $(seq 1 240); do
    if curl -s -m 2 "http://127.0.0.1:${PORT}/health" 2>/dev/null | grep -q '"ok"'; then
      ok=1; break
    fi
    docker ps --format '{{.Names}}' | grep -q '^qwen38$' || break
    sleep 1
  done
  if [ "$ok" != 1 ]; then
    printf "%-18s LOAD_FAILED\n" "$tag" | tee -a "$LOG"
    docker logs qwen38 2>&1 | tail -12 | tee -a "$LOG"
    return 1
  fi

  local used free
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)

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
    raise SystemExit(0)
t = r.get("timings") or {}
u = r.get("usage") or {}
print(json.dumps({
    "gen": round(float(t.get("predicted_per_second") or 0), 1),
    "read": round(float(t.get("prompt_per_second") or 0), 1),
    "out": u.get("completion_tokens", 0),
    "draft_n": t.get("draft_n"),
    "draft_n_accepted": t.get("draft_n_accepted"),
}))
PY
)
  echo "{\"tag\":\"$tag\",\"spec\":\"$spec\",\"ctx\":$ctx,\"kv\":\"$kv\",\"used_mib\":$used,\"free_mib\":$free,\"probe\":$result}" >> "$OUT/fit-raw.jsonl"
  python3 -c '
import json, sys
tag, spec, ctx, kv, used, free, raw = sys.argv[1:]
d = json.loads(raw)
gen = float(d.get("gen") or 0)
verdict = "FITS" if gen > 60 else ("SPILLED" if gen > 0 else "NO_RESPONSE")
print(f"{tag:<18} spec={spec:<28} ctx={ctx:<6} kv={kv:<4} used={used:>5} free={free:>4} gen={gen:>6} {verdict}")
' "$tag" "$spec" "$ctx" "$kv" "$used" "$free" "$result" | tee -a "$LOG"
}

run_matrix() {
  local only=${1:-}
  echo "# fitngram $(date -Iseconds)  image=$IMAGE  target=$TARGET" | tee "$LOG"
  echo "$MATRIX" | while read -r tag spec nmax ctx kv batch; do
    [ -z "$tag" ] && continue
    [ -n "$only" ] && [ "$tag" != "$only" ] && continue
    probe_one "$tag" "$spec" "$nmax" "$ctx" "$kv" "$batch" || true
  done
}

case "${1:-all}" in
  all) run_matrix ;;
  one) run_matrix "${2:?tag}" ;;
  *) echo "usage: $0 [all|one <tag>]"; exit 1 ;;
esac
