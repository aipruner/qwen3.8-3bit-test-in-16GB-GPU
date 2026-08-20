# DFlash 2 notes (2026-08-21)

Source recipe: BuffMcBigHuge on r/LocalLLaMA,
[Large Context w/ MTP, DFlash2, ngram-mod, Testing Qwen3.8-27B on 16GB VRAM](https://www.reddit.com/r/LocalLLaMA/comments/1vt3cpw/large_context_w_mtp_dflash2_ngrammod_testing/).
They ran `RVN-IQ3_XXS` + `Qwen3.8-27B-DFlash2-Q4_K_M` on a 4080 16GB, with
`--spec-type draft-dflash,ngram-mod --spec-draft-n-max 5 -c 105000 -ctk q5_1`.

This file is what happened when the same DFlash 2 GGUF was paired with **our**
target (`UD-Q3_K_XL`) on an RTX 5070 Ti 16GB.

## Runtime

Stock `ghcr.io/ggml-org/llama.cpp:full-cuda` understands DFlash **1** only:

```
llama_model_load: error loading model: done_getting_tensors: wrong number of tensors; expected 81, got 58
```

DFlash 2 needs llama.cpp [PR #27342](https://github.com/ggml-org/llama.cpp/pull/27342)
(commit `5ecbe1a`). Build:

```bash
./ops/build-dflash2-image.sh   # tags local/llama.cpp:dflash2-cuda, CUDA arch 120
./ops/qwen38.sh dflash
```

Draft GGUF: `z-lab/Qwen3.8-27B-DFlash2-GGUF` → `Qwen3.8-27B-DFlash2-Q4_K_M.gguf` (1.14 GB).

## VRAM ladder (GPU-resident draft)

`Say OK.` 32-token probes. Health = generation speed > 60 tokens/sec.

Reddit's n-max 5 / q5_1 / 16K–105K **spills** on `UD-Q3_K_XL` (2–4 tokens/sec, or timeout).
The extra 1.1 GiB draft plus n-max 5 compute buffers eat the headroom that MTP spent on context.

Working point:

| spec | ctx | KV | n-max | batch | used | free | 32-tok gen |
|---|---:|---|---:|---|---:|---:|---:|
| draft-dflash | 8192 | q8_0 | 4 | 256/128 | 15069 | 927 | 68.2 |
| draft-dflash | 8192 | q4_0 | 3 | 256/128 | 14791 | 1205 | 65.5 |
| draft-mtp (same image) | 8192 | q8_0 | 4 | default | 14239 | 1757 | (see specspeed) |

Draft on CPU (`--n-gpu-layers-draft 0`) fits 16K q8_0 but only ~38 tokens/sec.

## 600-token specspeed (cache-busted, `reasoning_effort=low`)

Same llama.cpp PR build, same 8K q8_0, same prompts.

| output | DFlash 2 n-max 4 | native MTP n-max 4 |
|---|---:|---:|
| Python LRU | 114.4 | 110.0 |
| HTML canvas | 110.4 | 121.6 |
| English prose | 81.3 | 76.7 |
| Traditional Chinese prose | 62.7 | 80.7 |
| **mean** | **92.2** | **97.2** |

DFlash 2 accept rates: code 458/528 (87%), HTML 452/587 (77%),
English prose 398/795 (50%), Chinese prose 340/1031 (33%).

## What this means

- DFlash 2 is **not** free VRAM-wise. On this 3-bit file it buys speed only if you
  give up most of the context window (24K MTP → 8K DFlash 2).
- At that 8K working point, mean generation speed is **within noise of MTP**,
  except Chinese prose where MTP is clearly faster.
- The Reddit 105K number used a smaller IQ3_XXS target. Do not expect it on
  `UD-Q3_K_XL`.
- ngram-mod is still untrusted here: prefix cache inflates it. `specspeed.py` salts
  every prompt. We did not promote ngram-mod into the default `dflash` profile.

## Quality suite (same harness as the 2026-08-19 MTP article)

Server: `./ops/qwen38.sh dflash` (8K, q8_0, n-max 4, GPU draft).
Sampling: `temperature=0.7, top_p=0.8, reasoning_effort=medium`.
Logs: `harness/results/dflash2/`.

| Test | MTP 24K (2026-08-19) | DFlash 2 8K (2026-08-21) |
|---|---|---|
| QuixBugs, 29 programs | 27/29 · 589 s · 175 calls · 0 bad JSON · 0 cheats. Fail: `lis`, `subsequences` | 28/29 · 738 s · 165 calls · 0 bad JSON · 0 cheats. Fail: `lis` only |
| Tetris ×3 | 3/3 playable, avg 35 s | 3 generated, avg 38 s, 14/14 feature checks. `node --check` 2/3 (run 3: `Unexpected token 'else'`) |
| Math, think only | 4/8 · 406 s · 43,015 tokens | 3/8 · 451 s · 45,609 tokens. Five failures all `got=None` at 8,000 output tokens |
| Math, Python tool | 8/8 · 123 s · 25,754 tokens | 7/8 · 336 s · 30,280 tokens. Fail: Q2 (Pell equation), 169 s, 6,959 output tokens, 2 tool calls, no `ANSWER:` |

QuixBugs mean generation speed during the agent loop was 60.5 tokens/sec
(MTP 24K run was ~90–110). `lis` failed both times. `subsequences` passing
this time is one sample at `temperature=0.7`, not a claim that DFlash 2
repairs better.

The 8K window is the quality cost. Q2 with tools filled the context and
truncated before `ANSWER:`. Pure-reason failures are the same "thought until
`max_tokens`" pattern as the first article, with a tighter ceiling.

## What we did not run

- ngram-mod on the quality suite (profile `dflash-ngram` exists; prefix cache
  makes speed claims from unsalt-ed prompts untrustworthy)
- Their target quant (`RVN-IQ3_XXS`) or their 105K / q5_1 / n-max 5 flags as a
  *working* config on `UD-Q3_K_XL`
- froggeric chat template
- The pelican / `reasoning_effort` sweep from the first article (that was 24K MTP)

Daily driver after this retest: `./ops/qwen38.sh safe` (24K native MTP).
