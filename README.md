# Qwen3.8-27B 3-bit test harness (16GB GPU)

The code and raw results from measuring **Qwen3.8-27B at 3-bit on a single RTX 5070 Ti (16GB)**.

Two server configs, same target GGUF, same machine:

1. **Native MTP** (Multi-Token Prediction) at 24K context — 2026-08-19. This is the daily driver.
2. **DFlash 2** at 8K context — 2026-08-21. A retest of a viral r/LocalLLaMA recipe, *not* a speed upgrade on this file.

> 這裡是實測程式碼與原始結果。第一篇是 24K 原生 MTP；後來網路上有人用 DFlash 2 在 16GB 卡上開到 105K，我拿**同一個** 3-bit 檔重跑，結論寫在下面。

If you are an agent picking this repo up: read **`CLAUDE.md`**, then **`docs/README.md`**, then **`docs/05-dflash2.md`**. Do not copy Reddit flags onto `UD-Q3_K_XL`.

---

## Setup under test

| | MTP (`safe`) | DFlash 2 (`dflash`) |
|---|---|---|
| Target | [`unsloth/Qwen3.8-27B-GGUF`](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) → `Qwen3.8-27B-UD-Q3_K_XL.gguf` (12.51 GiB) | same |
| Draft | MTP head already inside the GGUF (`blk.64.nextn.*`) | [`z-lab/Qwen3.8-27B-DFlash2-GGUF`](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2-GGUF) → `Qwen3.8-27B-DFlash2-Q4_K_M.gguf` (~1.14 GiB extra) |
| Image | `ghcr.io/ggml-org/llama.cpp:full-cuda` | `local/llama.cpp:dflash2-cuda` (llama.cpp [PR #27342](https://github.com/ggml-org/llama.cpp/pull/27342)) |
| GPU | RTX 5070 Ti 16GB (sm_120 Blackwell), WSL2 Ubuntu 24.04 | same |
| Flags | `-c 24576 -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --spec-draft-n-max 4` | `-c 8192 -ctk q8_0 -ctv q8_0 -b 256 -ub 128 --spec-type draft-dflash --spec-draft-n-max 4 --n-gpu-layers-draft 99` |
| Endpoint | `http://127.0.0.1:18038/v1` | same |
| Sampling | `temperature=0.7, top_p=0.8` | same (not the Reddit 1.0 / 0.95 / 20) |

Qwen3.8-27B is a *dense* model — every token activates all 27B parameters, so the whole thing has to sit in VRAM. 3-bit is not a preference here, it is what fits. 4-bit (`IQ4_XS`) spills on this card (~0.4 tokens/sec).

The Reddit post that triggered the DFlash 2 retest used a **smaller** target (`RVN-IQ3_XXS`) on a 4080 16GB and opened 105K context. Clipping: `docs/sources/reddit-buffmcbighuge-dflash2.md`. That recipe **spills** on `UD-Q3_K_XL` (2–4 tokens/sec or timeout). The extra draft GGUF eats the VRAM that native MTP spent on a 24K window.

Stock `full-cuda` only loads DFlash **1**. DFlash **2** GGUFs fail with `expected 81, got 58` tensors until you build PR #27342 (`./ops/build-dflash2-image.sh`).

---

## What the numbers said

### 2026-08-19 — native MTP, 24K

| Test | Result |
|---|---|
| QuixBugs, 29 programs | 27 / 29 · 589 s · 175 tool calls · 0 malformed JSON · 0 cheats |
| 2048 core logic, 19 hidden assertions | 5 / 5 generations passed |
| Tetris, ~400 lines one shot | 3 / 3 playable, avg 35 s |
| 8 math problems, pure reasoning | 4 / 8 · 406 s · 43,015 tokens |
| 8 math problems, with a Python tool | 8 / 8 · 123 s · 25,754 tokens |
| Generation speed by output type | tool calls 111–115 tokens/sec · Chinese prose ~80 |
| IQ4_XS (4-bit) at 8K context | 0.4 tokens/sec — spills, does not run |

Raw log: `harness/quixbugs-results.log`.

### 2026-08-21 — DFlash 2, 8K, same target GGUF

Fair 600-token specspeed, cache-busted, `reasoning_effort=low`, **same llama.cpp PR image**, 8K q8_0:

| output | DFlash 2 n-max 4 | native MTP n-max 4 |
|---|---:|---:|
| Python LRU | 114.4 | 110.0 |
| HTML canvas | 110.4 | 121.6 |
| English prose | 81.3 | 76.7 |
| Traditional Chinese prose | 62.7 | 80.7 |
| **mean** | **92.2** | **97.2** |

DFlash 2 draft accept: code 87% · HTML 77% · English prose 50% · Chinese prose 33%.

Same quality harness:

| Test | DFlash 2 8K |
|---|---|
| QuixBugs | **28 / 29** · 738 s · 165 calls · 0 bad JSON · 0 cheats. Fail: `lis` (also failed on MTP). `subsequences` passed this time |
| Tetris ×3 | avg 38 s · 14/14 feature checks · `node --check` **2/3** (run 3: `Unexpected token 'else'`) |
| Math, think only | **3 / 8** · 451 s · 45,609 tokens. Failures all `got=None` at 8,000 output tokens |
| Math, Python tool | **7 / 8** · 336 s · 30,280 tokens. Fail: Q2 (Pell equation) truncated, 169 s, no `ANSWER:` |

Agent-loop mean generation speed on QuixBugs was 60.5 tokens/sec (MTP 24K run was ~90–110). The 8K window is the cost: Q2 with tools filled the context.

**Takeaway:** on `UD-Q3_K_XL`, DFlash 2 is not a free speedup. It trades the 24K window for an extra 1.1 GiB draft, and at the 8K point that still fits, mean generation speed is within noise of native MTP (Chinese prose is worse). Keep `./ops/qwen38.sh safe` as the daily driver. DFlash 2 is interesting if you switch to a *smaller* target quant that still has VRAM for both the draft **and** a long context — which is what the Reddit post actually did.

Logs: `harness/results/dflash2/` and `harness/results/mtp/specspeed-8k.log`. Narrative: `docs/05-dflash2.md`.

ngram-mod is **not** the default. llama.cpp prefix cache inflates unsalt-ed ngram numbers. `harness/specspeed.py` salts every prompt. Profile `dflash-ngram` exists; the quality suite did not run on it.

---

## What the scripts measure

| Script | What it does |
|---|---|
| `harness/agent.py` | Minimal ReAct agent — `list_dir` / `read_file` / `write_file` / `run_tests` |
| `harness/quixfix.py` | 29 [QuixBugs](https://github.com/jkoppel/QuixBugs) programs. Fresh sandbox per run; the harness re-runs tests; test-file MD5 before/after catches cheats |
| `harness/game2048.py` | 2048 core logic + 19 hidden assertions |
| `harness/tetris.py` | One-shot playable Tetris, syntax- and feature-checked |
| `harness/mathtest.py` | 8 hard math problems, `reason` or `tool` |
| `harness/truth.py` | Brute-forces the math ground truth locally |
| `harness/specspeed.py` | Cache-busted generation speed by output type (code / HTML / EN prose / ZH prose) |
| `harness/toolstress.py` | Nested-schema tool-call stress test |
| `harness/ctx3.py` | Context-length speed scan, salted |
| `harness/fit.sh`, `fitlean.sh`, `fitdflash.sh` | VRAM fit ladders. Health = measured generation speed, not `/health` |
| `harness/run_dflash2_suite.sh` | specspeed + math + Tetris + QuixBugs into `harness/results/$SPEC_TAG/` |
| `ops/qwen38.sh` | Launcher. Profiles: `safe` / `agent` / `long` / `vision` / `dflash` / `dflash-ngram` |
| `ops/build-dflash2-image.sh` | Docker build of llama.cpp PR #27342, CUDA arch 120 |

Fixtures: `harness/proj_template/`, `harness/proj_hard/`. Charts: `harness/charts/`.

---

## Running it

```bash
./ops/qwen38.sh safe       # 24K native MTP — daily driver, stock image
./ops/qwen38.sh status     # VRAM, health, endpoint
./ops/qwen38.sh stop
```

DFlash 2 (one-time image build, then):

```bash
./ops/build-dflash2-image.sh
./ops/qwen38.sh dflash
SPEC_TAG=dflash2 ./harness/run_dflash2_suite.sh
```

Then:

```bash
git clone https://github.com/jkoppel/QuixBugs.git QuixBugs-master
export QWEN_URL=http://127.0.0.1:18038/v1
python3 harness/quixfix.py --effort medium
python3 harness/mathtest.py tool medium
python3 harness/mathtest.py reason medium
python3 harness/tetris.py 3
python3 harness/specspeed.py
python3 harness/truth.py
```

Only `unittest` is required — no pytest, no matplotlib.

Model files live outside the repo: `/home/kino/models/qwen3.8-27b/`. Config: `~/.config/qwen38.env`. `~/.local/bin/qwen38` should symlink to **this** `ops/qwen38.sh`.

**Traps that silently ruin numbers:**

- **llama.cpp prefix cache.** Repeat the same prompt and prefill / ngram drafts replay. `specspeed.py` and `ctx3.py` prepend a random salt. Do the same in any new benchmark.
- **WSL2 does not report OOM.** The server starts, `/health` returns `ok`, the API responds — generation is just ~300× slower. Judge health by measured generation speed. Below ~60 tokens/sec is spilled. `fitlean.sh` / `fitdflash.sh` send a 32-token probe.
- **Thinking tokens count against `max_tokens`.** Give ≥1200 or `content` comes back empty. `reasoning_effort` is only `low` / `medium` / `xhigh`.
- **Stock Docker image ≠ DFlash 2 image.** `dflash*` profiles switch to `local/llama.cpp:dflash2-cuda` automatically.
- **QuixBugs.** Not vendored. Exclude `knapsack` and `levenshtein` (even the official fix times out).
- Do not commit `.gguf` files or `QuixBugs-master/`.

---

## Directory map (for the next agent)

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Short project instructions. Read first |
| `docs/README.md` | Index of session notes |
| `docs/05-dflash2.md` | DFlash 2 fit ladder + quality numbers |
| `ops/qwen38.sh` | Launcher. Source of truth for flags |
| `harness/results/dflash2/` | 2026-08-21 raw logs |
| `harness/results/mtp/` | 8K MTP specspeed on the same PR image (fair speed A/B) |
| `harness/quixbugs-results.log` | 2026-08-19 MTP QuixBugs |
| `output/qwen38-dflash2-*.md` | Follow-up article drafts (Medium / Threads / Zhihu / X) |
| `output/images/` | Charts and Tetris screenshots from the first article |

Voice for any new article: first person, vernacular, numbers over adjectives. Spell out `token`, 「生成速度」, 「讀取速度」. Expand MTP on first use. No "Windows desktop ate VRAM". Do not invent a measurement.

---

## Credits

- **QuixBugs** — [jkoppel/QuixBugs](https://github.com/jkoppel/QuixBugs) (MIT). Lin, Koppel, Chen, Solar-Lezama, *QuixBugs: A Multi-Lingual Program Repair Benchmark Set*, SPLASH Companion 2017.
- **Model** — [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B), Apache 2.0.
- **Quantization** — [Unsloth Dynamic GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF).
- **DFlash 2 draft** — [z-lab/Qwen3.8-27B-DFlash2-GGUF](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2-GGUF). llama.cpp support: [PR #27342](https://github.com/ggml-org/llama.cpp/pull/27342).
- **Recipe that prompted the retest** — BuffMcBigHuge, [r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/comments/1vt3cpw/large_context_w_mtp_dflash2_ngrammod_testing/).

Code in this repository is MIT-licensed. QuixBugs is not vendored here — clone it separately.
