#!/usr/bin/env python3
"""Show when ngram-mod helps.

- unique: salted prompt (ngram should not replay a previous request)
- repeat: identical prompt twice; the second hit is prefix-cache + ngram
- tools:  ask for many near-identical JSON tool-call lines (agent-shaped output)

Do not treat `repeat` as a published generation-speed number. It is a demo of
the cache/ngram trap, not a fair benchmark.
"""
from __future__ import annotations

import json, os, random, string, time, requests

BASE = os.environ.get("QWEN_URL", "http://127.0.0.1:18038/v1").rstrip("/")
TAG = os.environ.get("SPEC_TAG", "ngramdemo")
OUT = os.environ.get("SPEC_OUT", "")
MAXTOK = int(os.environ.get("MAXTOK", "400"))
EFFORT = os.environ.get("EFFORT", "low")

UNIQUE = (
    "Write a Python class implementing an LRU cache with get/put in O(1). "
    "Code only, no explanation."
)
REPEAT = UNIQUE
TOOLS = (
    "Output exactly 25 lines. Each line is one JSON object and nothing else. "
    "Line i (1-based) must be: "
    '{"name":"read_file","arguments":{"path":"src/mod_i.py"}} '
    "with i filled in. No markdown, no extra keys, no commentary."
)


def salt() -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(24))


def ask(prompt: str) -> dict:
    t0 = time.time()
    r = requests.post(
        BASE + "/chat/completions",
        json={
            "model": "qwen3.8-27b",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "top_p": 0.8,
            "max_tokens": MAXTOK,
            "reasoning_effort": EFFORT,
        },
        timeout=1200,
    ).json()
    wall = time.time() - t0
    if "choices" not in r:
        return {"err": str(r)[:300], "wall": round(wall, 2)}
    t = r.get("timings") or {}
    u = r.get("usage") or {}
    return {
        "wall": round(wall, 2),
        "gen": round(float(t.get("predicted_per_second") or 0), 1),
        "read": round(float(t.get("prompt_per_second") or 0), 1),
        "out": u.get("completion_tokens", 0),
        "draft_n": t.get("draft_n"),
        "draft_n_accepted": t.get("draft_n_accepted"),
        "finish": r["choices"][0].get("finish_reason"),
    }


def show(name: str, row: dict) -> None:
    extra = ""
    if row.get("draft_n") is not None:
        extra = f"  draft={row.get('draft_n')}/{row.get('draft_n_accepted')}"
    print(
        f"{name:<12} wall={row.get('wall', 0):6.1f}s  gen={row.get('gen', 0):6.1f} tok/s  "
        f"read={row.get('read', 0):6.0f}  out={row.get('out', 0)}{extra}",
        flush=True,
    )


def main() -> None:
    print(f"# ngramdemo tag={TAG} effort={EFFORT} max_tokens={MAXTOK} url={BASE}", flush=True)
    rows = {}
    rows["unique"] = ask(salt() + "\n" + UNIQUE)
    show("unique", rows["unique"])
    rows["repeat1"] = ask(REPEAT)
    show("repeat-1", rows["repeat1"])
    rows["repeat2"] = ask(REPEAT)
    show("repeat-2", rows["repeat2"])
    rows["tools"] = ask(salt() + "\n" + TOOLS)
    show("tools-json", rows["tools"])
    if OUT:
        os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
        with open(OUT, "w") as f:
            json.dump({"tag": TAG, "rows": rows}, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main()
