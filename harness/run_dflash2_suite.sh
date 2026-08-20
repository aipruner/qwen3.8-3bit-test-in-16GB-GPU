#!/usr/bin/env bash
# Run the DFlash2 comparison suite against whatever is currently serving
# at $QWEN_URL (default http://127.0.0.1:18038/v1).
#
# Usage:
#   SPEC_TAG=dflash2 ./harness/run_dflash2_suite.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TAG=${SPEC_TAG:-dflash2}
OUT="harness/results/${TAG}"
mkdir -p "$OUT"
export QWEN_URL="${QWEN_URL:-http://127.0.0.1:18038/v1}"
export QUIX_OUT="$OUT/quix_runs"

echo "==> specspeed  tag=$TAG  url=$QWEN_URL"
SPEC_TAG="$TAG" SPEC_OUT="$OUT/specspeed.json" python3 harness/specspeed.py | tee "$OUT/specspeed.log"

echo "==> mathtest tool"
python3 harness/mathtest.py tool medium | tee "$OUT/mathtest-tool.log"

echo "==> mathtest reason"
python3 harness/mathtest.py reason medium | tee "$OUT/mathtest-reason.log"

echo "==> tetris x3"
python3 harness/tetris.py 3 | tee "$OUT/tetris.log"

echo "==> quixfix 29"
python3 harness/quixfix.py --effort medium | tee "$OUT/quixfix.log"
if [ -f "$OUT/quix_runs/results.json" ]; then
  cp "$OUT/quix_runs/results.json" "$OUT/quixfix.json"
fi

echo "==> done. results in $OUT"
ls -l "$OUT"
