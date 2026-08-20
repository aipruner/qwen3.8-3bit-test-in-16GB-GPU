#!/usr/bin/env python3
"""Cache-busted generation-speed probe. Prints wall time, tokens/sec, and the
raw llama.cpp timings dict so draft acceptance is visible.

A random salt is prepended to every prompt. llama.cpp's prefix cache will
otherwise replay ngram drafts and inflate the numbers.
"""
from __future__ import annotations

import json, os, random, string, sys, time, requests

BASE = os.environ.get("QWEN_URL", "http://127.0.0.1:18038/v1").rstrip("/")
TAG = os.environ.get("SPEC_TAG", "run")
OUT = os.environ.get("SPEC_OUT", "")
MAXTOK = int(os.environ.get("MAXTOK", "600"))
EFFORT = os.environ.get("EFFORT", "low")

PROMPTS = [
    ("code", "Write a Python class implementing an LRU cache with get/put in O(1). Code only, no explanation."),
    ("code2", "Write a single-file HTML page with a canvas that draws an animated bouncing ball. Code only."),
    ("prose_en", "Explain in flowing English prose, with no lists and no code, why memory bandwidth limits dense transformer inference."),
    ("prose_zh", "用連貫的繁體中文散文解釋，為什麼記憶體頻寬會限制 dense transformer 的推論速度。不要條列、不要程式碼。"),
]


def salt() -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(24))


def one(name: str, prompt: str) -> dict:
    body = {
        "model": "qwen3.8-27b",
        "messages": [{"role": "user", "content": salt() + "\n" + prompt}],
        "temperature": 0.7,
        "top_p": 0.8,
        "max_tokens": MAXTOK,
        "reasoning_effort": EFFORT,
    }
    t0 = time.time()
    r = requests.post(BASE + "/chat/completions", json=body, timeout=1200).json()
    wall = time.time() - t0
    if "choices" not in r:
        return {"name": name, "err": str(r)[:300], "wall": wall}
    t = r.get("timings") or {}
    u = r.get("usage") or {}
    return {
        "name": name,
        "wall": round(wall, 2),
        "gen": round(float(t.get("predicted_per_second") or 0), 1),
        "read": round(float(t.get("prompt_per_second") or 0), 1),
        "out": u.get("completion_tokens", 0),
        "inn": u.get("prompt_tokens", 0),
        "finish": r["choices"][0].get("finish_reason"),
        "timings": t,
    }


def main() -> None:
    rows = []
    gens = []
    print(f"# specspeed tag={TAG} effort={EFFORT} max_tokens={MAXTOK} url={BASE}", flush=True)
    for name, prompt in PROMPTS:
        row = one(name, prompt)
        rows.append(row)
        gens.append(float(row.get("gen") or 0))
        extra = ""
        t = row.get("timings") or {}
        keys = [k for k in t if "draft" in k.lower() or "accept" in k.lower()]
        if keys:
            extra = "  " + " ".join(f"{k}={t[k]}" for k in keys)
        print(
            f"{name:<8} wall={row.get('wall', 0):6.1f}s  gen={row.get('gen', 0):6.1f} tok/s  "
            f"read={row.get('read', 0):6.0f} tok/s  out={row.get('out', 0)}{extra}",
            flush=True,
        )
        if "err" in row:
            print("  ERR", row["err"][:200], flush=True)
    mean = sum(gens) / len(gens) if gens else 0
    print(f"mean gen = {mean:.1f} tok/s", flush=True)
    payload = {"tag": TAG, "effort": EFFORT, "mean_gen": round(mean, 1), "rows": rows}
    if OUT:
        os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
        with open(OUT, "w") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main()
