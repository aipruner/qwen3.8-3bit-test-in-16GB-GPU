# Project instructions — qwen3.8test

Harness and evidence for running **Qwen3.8-27B at 3-bit on one RTX 5070 Ti (16GB)**.
First-person write-ups live in `output/` (gitignored except images). Code and raw
results are what this repo publishes.

## Tech stack

- Python 3 stdlib + `requests`. Tests use `unittest`, never pytest.
- Charts: HTML + CSS in `harness/charts/`, screenshotted with headless Chromium.
- Runtime: llama.cpp in Docker, OpenAI-compatible endpoint at `http://127.0.0.1:18038/v1`.
- Model files live outside the repo: `/home/kino/models/qwen3.8-27b/`.

## Voice (articles / Threads / X / Zhihu)

Copy the author's existing posts, do not invent a new persona.

- First person, vernacular, short sentences, numbers over adjectives.
- Spell things out: `token` not `tok`, 「生成速度」not `tg`, 「讀取速度」not `pp`,
  「首字延遲」not `TTFT`. Expand MTP as Multi-Token Prediction on first use.
- Short headings. No origin-story padding. No "Windows desktop ate 2GB VRAM".
- Do not invent measurements. If a run did not finish, say so.

## Commands

```bash
./ops/qwen38.sh safe           # daily driver: 24K native MTP (stock full-cuda)
./ops/qwen38.sh safe-ngram     # 24K MTP + ngram-mod (dflash2 image)
./ops/qwen38.sh dflash         # DFlash 2 at 8K q8_0 n-max 4
./ops/qwen38.sh dflash-ngram   # DFlash 2 + ngram at 8K q4_0 n-max 3
./ops/qwen38.sh status
python3 harness/specspeed.py
python3 harness/ngramdemo.py
python3 harness/mathtest.py tool medium
python3 harness/quixfix.py
SPEC_TAG=mtp-ngram ./harness/run_ngram_suite.sh
```

Rebuild the DFlash 2 image after pulling llama.cpp PR #27342:

```bash
./ops/build-dflash2-image.sh
```

## Directory map

| Path | Purpose |
|---|---|
| `ops/qwen38.sh` | Launcher. Source of truth. `~/.local/bin/qwen38` should symlink here. |
| `ops/build-dflash2-image.sh` | Docker build of llama.cpp PR #27342, CUDA arch 120 |
| `harness/*.py` | Measurement scripts against `$QWEN_URL` |
| `harness/results/` | Dated raw logs/JSON from a run |
| `harness/proj_template/`, `proj_hard/` | Fixtures for `agent.py` |
| `docs/` | Local research notes (tracked). `output/` is the public write-up staging area |

## Hard-won traps

- WSL2 does not report OOM. Judge a config by **measured generation speed**, not `/health`.
  Below ~60 tokens/sec means weights spilled to system memory.
- llama.cpp prefix cache inflates ngram and repeated-prompt benchmarks. Salt every prompt.
- One CPU-offloaded layer costs ~60% generation speed on this hybrid architecture.
- `reasoning_effort` is `low` / `medium` / `xhigh`. Other values 500 the request.
- Thinking tokens count against `max_tokens`. Give ≥1200 or `content` comes back empty.
- Stock `ghcr.io/ggml-org/llama.cpp:full-cuda` loads DFlash **1**. DFlash **2** GGUFs
  (`expected 81, got 58` tensors) need PR #27342.
- QuixBugs is not vendored. `quixfix.py` expects `QuixBugs-master/` next to `harness/`.
  Exclude `knapsack` and `levenshtein`: even the official fix times out.
- Do not commit `.gguf` files or `QuixBugs-master/`.

## Config under test (2026-08)

| | MTP (`agent` / `safe`) | DFlash 2 (`dflash`) |
|---|---|---|
| Target | `Qwen3.8-27B-UD-Q3_K_XL.gguf` | same |
| Draft | native MTP head in the GGUF | `Qwen3.8-27B-DFlash2-Q4_K_M.gguf` (~1.1 GiB extra) |
| Image | `ghcr.io/ggml-org/llama.cpp:full-cuda` | `local/llama.cpp:dflash2-cuda` |
| Typical flags | `-c 24576 -ctk q8_0 --spec-type draft-mtp --spec-draft-n-max 4` | `-c 8192 -ctk q8_0 -b 256 -ub 128 --spec-type draft-dflash --spec-draft-n-max 4` |

Sampling for the harness is the original article's `temperature=0.7, top_p=0.8`,
not the Reddit post's 1.0 / 0.95 / 20, so quality numbers stay comparable.

Do not use `agent` (32K) as the published MTP config — it spills on this card.
`safe` is the 24K setup from the first article.

DFlash 2 quality vs that 24K MTP baseline (2026-08-21, logs in
`harness/results/dflash2/`): QuixBugs 28/29 vs 27/29 but 738 s vs 589 s;
math+tool 7/8 vs 8/8 (Q2 truncated at 8K); think-only 3/8 vs 4/8;
Tetris avg 38 s, `node --check` 2/3. Mean 8K specspeed 92.2 vs MTP 97.2
tokens/sec; Chinese prose 62.7 vs 80.7. Details: `docs/05-dflash2.md`.

ngram-mod stacked on both (same night, `docs/06-ngram.md`):
`safe-ngram` 24K q8_0 vs `dflash-ngram` 8K q4_0 n-max 3.
QuixBugs 28/29 in 492 s (mean 105.2 tokens/sec) vs 24/29 in 783 s (78.0).
Salted specspeed mean 94.6 vs 78.0. 16K q4_0 DFlash+ngram 32-token probe
was a false FITS (600-token write 5.1 tokens/sec). Agent winner: MTP+ngram.
