# ngram-mod + MTP vs ngram-mod + DFlash 2 (2026-08-21)

Reddit (BuffMcBigHuge) stacked **ngram-mod** on both neural drafts. Our first
DFlash 2 retest did **not**. This file is the follow-up on `UD-Q3_K_XL`.

## What ngram-mod is

llama.cpp [PR #19164](https://github.com/ggml-org/llama.cpp/pull/19164).
It is **not** a second model.

It keeps a hash table of recent token n-grams (~4M slots, on the order of
**16 MiB RAM**, not VRAM). When the last N tokens match something already
seen, it proposes the tokens that followed last time. The target model still
verifies every token.

It helps when the output **repeats a shape**: JSON tool calls, identical
HTML/CSS fragments, copy-pasted code. It does almost nothing on unique Chinese
prose. llama.cpp's **prefix cache** makes a second identical prompt look even
faster — that is why `specspeed.py` salts every request, and why `ngramdemo.py`
keeps a separate `repeat-2` row that must not be published as a fair speed.

Flags used here (same as the Reddit recipe):

```
--spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32
```

`--spec-type` is a comma list. Neural draft and ngram stack:

- `draft-mtp,ngram-mod` → profile `safe-ngram` (24K q8_0, n-max 4, no extra GGUF)
- `draft-dflash,ngram-mod` → profile `dflash-ngram` (8K q4_0, n-max 3, +1.1 GiB draft)

32-token probes lie. `dflash-ngram` at 16K q4_0 n-max 4 scored 60.8 on
`Say OK.` then **5.1 tokens/sec** on a 600-token write. Published profile
is the 8K q4_0 n-max 3 point that held 92.0 tokens/sec at 600 tokens.

They do **not** stack with each other. `draft-mtp,draft-dflash` is not a thing.

ngram does not buy KV cache. Max context is still set by the target quant plus
whether a DFlash GGUF is resident.

## Commands

```bash
./harness/fitngram.sh
QWEN38_FORCE=1 ./ops/qwen38.sh safe-ngram
SPEC_TAG=mtp-ngram ./harness/run_ngram_suite.sh
QWEN38_FORCE=1 ./ops/qwen38.sh dflash-ngram
SPEC_TAG=dflash-ngram ./harness/run_ngram_suite.sh
```

Both ngram profiles use `local/llama.cpp:dflash2-cuda` so the build matches.

## Fit ladder (2026-08-21 night, idle ~700 MiB)

32-token probes. Health = generation speed > 60 tokens/sec. Same
`local/llama.cpp:dflash2-cuda` image. Log: `harness/results/ngram/fit.log`.

| spec | ctx | KV | used | free | 32-tok gen | verdict |
|---|---:|---|---:|---:|---:|---|
| draft-mtp,ngram-mod | 8192 | q8_0 | 14848 | 1148 | 83.9 | FITS |
| draft-mtp,ngram-mod | 16384 | q8_0 | 15166 | 830 | 72.8 | FITS |
| draft-mtp,ngram-mod | **24576** | q8_0 | 15472 | 524 | 73.8 | **FITS — `safe-ngram`** |
| draft-mtp,ngram-mod | 32768 | q8_0 | 15529 | 467 | 0.1 | SPILLED |
| draft-dflash,ngram-mod | 8192 | q8_0 | 15500 | 496 | 4.2 | SPILLED |
| draft-dflash,ngram-mod | 12288 | q8_0 | 15588 | 408 | 3.8 | SPILLED |
| draft-dflash,ngram-mod | 16384 | q8_0 | 15659 | 337 | 2.5 | SPILLED |
| draft-dflash,ngram-mod | **16384** | q4_0 | 15455 | 541 | 60.8 | **FITS — `dflash-ngram`** |
| draft-dflash,ngram-mod | 24576 | q4_0 | 15562 | 434 | 0.2 | SPILLED |

ngram did **not** raise the context ceiling. MTP still maxes at 24K q8_0.
A 16K q4_0 DFlash + ngram 32-token probe said FITS (60.8) then a 600-token
write ran at **5.1 tokens/sec**. Treat 32-token probes as a spill screen,
not a working-point proof.

Working DFlash + ngram point used for the suite: **8K, q4_0, n-max 3**,
batch 256. 600-token write 92.0 tokens/sec. Log extras in the 680681 probe
(`8k q4_0 n-max 4` = 4.2 spilled; `4k q8_0 n-max 4` = 105.4 but unusable
for an agent).

## Suites (same harness, `temperature=0.7, top_p=0.8`)

| | MTP + ngram `safe-ngram` | DFlash 2 + ngram `dflash-ngram` |
|---|---|---|
| Window | 24K q8_0 n-max 4 | 8K q4_0 n-max 3 |
| specspeed mean (salted 600-token) | **94.6** tokens/sec | **78.0** |
| Chinese prose | 73.7 | 59.7 |
| tool-json demo | 124.5 (draft 313/342) | 109.1 (295/312) |
| Math + Python tool | 7/8 · 254 s · Q2 truncated | **8/8** · 310 s |
| QuixBugs 29 | **28/29** · 492 s · 171 calls · mean 105.2 tokens/sec · fail `lis` | **24/29** · 783 s · 162 calls · mean 78.0 · fail `find_first_in_sorted`, `kheapsort`, `lis`, `sqrt`, `subsequences` |
| bad JSON / cheats | 0 / 0 | 0 / 0 |

Logs: `harness/results/mtp-ngram/`, `harness/results/dflash-ngram/`.

Agent takeaway on this file: **ngram + MTP**. Larger window, faster repair
loop, four more QuixBugs passes. ngram + DFlash 2 does not open more
context than MTP; it spends VRAM on the extra GGUF and the 8K ceiling
shows up as more stalls.
