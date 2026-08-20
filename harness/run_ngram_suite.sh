#!/usr/bin/env bash
# Agent-facing suite for whatever is currently serving at $QWEN_URL.
# Intended for safe-ngram and dflash-ngram. Skips think-only math and Tetris:
# those are not the ngram question.
#
# Usage:
#   SPEC_TAG=mtp-ngram ./harness/run_ngram_suite.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TAG=${SPEC_TAG:-ngram}
OUT="harness/results/${TAG}"
mkdir -p "$OUT"
export QWEN_URL="${QWEN_URL:-http://127.0.0.1:18038/v1}"
export QUIX_OUT="$ROOT/$OUT/quix_runs"

echo "==> specspeed (salted, unique)  tag=$TAG"
SPEC_TAG="$TAG" SPEC_OUT="$OUT/specspeed.json" python3 harness/specspeed.py | tee "$OUT/specspeed.log"

echo "==> ngramdemo (unique / repeat / tool-json)"
SPEC_TAG="$TAG" SPEC_OUT="$OUT/ngramdemo.json" python3 harness/ngramdemo.py | tee "$OUT/ngramdemo.log"

echo "==> mathtest tool"
python3 harness/mathtest.py tool medium | tee "$OUT/mathtest-tool.log"

echo "==> quixfix 29"
python3 harness/quixfix.py --effort medium | tee "$OUT/quixfix.log"
if [ -f "$OUT/quix_runs/results.json" ]; then
  cp "$OUT/quix_runs/results.json" "$OUT/quixfix.json"
fi

echo "==> done. results in $OUT"
ls -l "$OUT"
