# Qwen3.8-27B 3-bit test harness (16GB GPU)

The code I used to measure **Qwen3.8-27B at 3-bit on a single RTX 5070 Ti (16GB)**, plus the raw
results it produced. Everything here was run on one machine on **2026-08-19** against a local
llama.cpp server.

This repo is the harness and the evidence — not a write-up.

> 這裡是我實測 Qwen3.8-27B 3-bit 用的測試程式碼與原始結果。

---

## Setup under test

| | |
|---|---|
| Model | [`unsloth/Qwen3.8-27B-GGUF`](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) → `Qwen3.8-27B-UD-Q3_K_XL.gguf` (12.51 GiB) |
| Runtime | `ghcr.io/ggml-org/llama.cpp:full-cuda`, Docker |
| GPU | RTX 5070 Ti 16GB (sm_120 Blackwell), WSL2 Ubuntu 24.04 |
| Flags | `-ngl 99 -fa 1 --jinja --parallel 1 -c 24576 -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --spec-draft-n-max 4` |
| Endpoint | `http://127.0.0.1:8088/v1` (OpenAI-compatible) |

Qwen3.8-27B is a *dense* model — every token activates all 27B parameters, so the whole thing has to
sit in VRAM. 3-bit is not a preference here, it is what fits.

---

## What the scripts measure

| Script | What it does |
|---|---|
| `harness/agent.py` | Minimal ReAct agent — `list_dir` / `read_file` / `write_file` / `run_tests` over the OpenAI-compatible endpoint |
| `harness/quixfix.py` | Runs the agent against 29 [QuixBugs](https://github.com/jkoppel/QuixBugs) programs. Each run gets a fresh sandbox; the verdict comes from the harness re-running the suite, never from the model claiming success. Test files are MD5-checked before and after, so editing the tests to go green is detected and counted as a failure |
| `harness/game2048.py` | Asks for 2048 core logic, then runs 19 hidden assertions against it (merge-once-per-move, no board mutation, `has_moves` on a full-but-mergeable board) |
| `harness/tetris.py` | Asks for a complete playable Tetris in one shot, then syntax- and feature-checks the output |
| `harness/mathtest.py` | 8 hard math problems in two modes: pure reasoning, and with a Python execution tool |
| `harness/truth.py` | Brute-forces the ground truth for every math answer locally, so the grading does not depend on a search result being right |
| `harness/toolstress.py` | Nested-schema tool-call stress test |
| `harness/ctx3.py` | Context-length speed scan, cache-busted with a random salt per request |
| `harness/fit.sh`, `harness/fitlean.sh` | Quantization × context "does it actually fit in VRAM" ladder, judged by measured generation speed |
| `harness/speed.py` | Generation speed by output type |
| `ops/qwen38.sh` | llama-server launcher (`agent` / `long` / `safe` / `vision` profiles) |

Supporting files: `harness/proj_template/` and `harness/proj_hard/` are fixture projects for
`agent.py`; `harness/tetris_runs/` holds the autoplay driver used to screenshot a board that was
really played; `harness/charts/` renders results as HTML + CSS for screenshotting.

---

## Raw results in this repo

- **`harness/quixbugs-results.log`** — one line per program: pass/fail, steps, tool calls, output
  tokens, wall-clock, generation speed.
- **`harness/quixbugs-results.json`** — the same run with full per-step detail.
- **`harness/screenshots/`** — the three generated Tetris builds, screenshotted mid-game after an
  automated play sequence (scores 342 / 402 / 352). Proof the generated games actually run.

Summary line from that log:

```
SUMMARY 27/29 passed  total_wall=589s
        total_tok=297636 (in 253553 / out 44083)  calls=175  bad=0  cheat=0
```

Other measurements, for reference:

| Test | Result |
|---|---|
| QuixBugs, 29 programs | 27 / 29 · 589 s · 175 tool calls · 0 malformed JSON · 0 cheats |
| 2048 core logic, 19 hidden assertions | 5 / 5 generations passed |
| Tetris, ~400 lines one shot | 3 / 3 playable, avg 35 s |
| 8 math problems, pure reasoning | 4 / 8 · 406 s · 43,015 tokens |
| 8 math problems, with a Python tool | 8 / 8 · 123 s · 25,754 tokens |
| Generation speed by output type | tool calls 111–115 t/s · code 100–113 · English prose 80–85 · Chinese prose ~80 |
| IQ4_XS (4-bit) at 8K context | 0.4 t/s — spills to system memory, does not run on this card |

---

## Running it

Start a llama.cpp server with an OpenAI-compatible endpoint on `http://127.0.0.1:8088/v1`:

```bash
./ops/qwen38.sh agent      # start
./ops/qwen38.sh status     # VRAM, health, endpoint
./ops/qwen38.sh stop
```

Then:

```bash
git clone https://github.com/jkoppel/QuixBugs.git QuixBugs-master
python3 harness/quixfix.py        # the 29-program repair run
python3 harness/mathtest.py       # the 8 math problems, both modes
python3 harness/truth.py          # recompute the ground truth yourself
python3 harness/ctx3.py           # context-length speed scan
./harness/fitlean.sh Qwen3.8-27B-UD-Q3_K_XL.gguf 24576 q8_0   # VRAM fit probe
```

Only `unittest` is required — no pytest, no matplotlib.

**Two traps that will silently ruin your numbers:**

- **llama.cpp's prefix cache.** Repeating the same prompt returns cached prefill and inflates your
  speeds. `ctx3.py` prepends a random salt to every request; do the same in your own benchmarks.
- **Under WSL2, exceeding VRAM does not report OOM.** The server starts, `/health` returns `ok`, the
  API responds — it is just ~300x slower. Judge health by *measured generation speed*, not by whether
  the process came up. `fitlean.sh` sends a 32-token probe and treats anything under 60 tokens/sec as
  spilled.

---

## Credits

- **QuixBugs** — [jkoppel/QuixBugs](https://github.com/jkoppel/QuixBugs) (MIT), 40 programs from the
  2011–2013 Quixey Challenge. Lin, Koppel, Chen, Solar-Lezama, *QuixBugs: A Multi-Lingual Program
  Repair Benchmark Set*, SPLASH Companion 2017.
- **Model** — [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B), Apache 2.0.
- **Quantization** — [Unsloth Dynamic GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF).

Code in this repository is MIT-licensed. QuixBugs is not vendored here — clone it separately.
