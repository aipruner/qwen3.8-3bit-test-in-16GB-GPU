# ngram is not a second model. Stacked on MTP, it is the better agent on this 16GB card

*Same 3-bit file. Same 5070 Ti. ngram + MTP vs ngram + DFlash 2: who opens a larger window, who actually repairs bugs.*

---

The last article crushed Qwen3.8-27B to 3-bit and ran the agent suite on the model's own MTP (Multi-Token Prediction — guess the next batch of tokens in one shot). Then someone on r/LocalLLaMA stacked **ngram-mod** on MTP and on DFlash 2 and opened ~100K context on a 16GB card.

I did not switch quants. Still `UD-Q3_K_XL`. Three questions: what ngram is, which stack opens more context, which one behaves like an agent.

Every number came off this machine. Sampling stays `temperature=0.7, top_p=0.8`. Same llama.cpp PR #27342 build for both.

---

## 0. What ngram-mod does

It is not a draft model. llama.cpp [PR #19164](https://github.com/ggml-org/llama.cpp/pull/19164) keeps a hash table of recent token n-grams (~4 million slots, on the order of **16 MB RAM**, almost no VRAM). When the last N tokens have been seen before, it proposes whatever followed last time. The target still verifies every token.

It is accurate on repeated *shapes*: JSON tool calls, similar HTML, copy-pasted code. Unique Chinese prose gets almost nothing.

It stacks with a neural draft via a comma in `--spec-type`:

- `draft-mtp,ngram-mod`
- `draft-dflash,ngram-mod`

MTP and DFlash 2 are still one-or-the-other. ngram also does **not** make KV cache cheaper. Max context is still the target quant plus whether a 1.1 GB draft GGUF is sitting on the GPU.

I copied their lookup sizes: `--spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32`.

Speed tests prepend a random salt. Otherwise llama.cpp's prefix cache makes the second identical prompt look fast, and that is not ngram.

---

## 1. Who opens more context: still MTP

32-token probes. Under 60 tokens/sec counts as spilled.

**ngram + MTP**

- 8K / 16K / **24K** q8_0 all hold (24K probe 73.8 tokens/sec)
- 32K spills (0.1)

**ngram + DFlash 2**

- 8K / 12K / 16K q8_0 all spill (2–4 tokens/sec)
- 16K q4_0 scored 60.8 on a 32-token probe. A 600-token write: **5.1 tokens/sec**. The probe lies.
- The working point that actually holds is **8K, q4_0, n-max 3**. 600-token write at 92.0 tokens/sec.

ngram did not grow the window. MTP is still 24K. DFlash 2 pays an extra draft and keeps a smaller window. Their 105K used a thinner target quant.

---

## 2. Unique text vs tool-call shape

Same build, salted prompts, ~600 tokens out:

**Generation speed (tokens/sec)**

- mean: ngram + MTP **94.6**, ngram + DFlash 2 **78.0**
- Python: 103.8 vs 94.7
- HTML: 120.5 vs 89.3
- English prose: 80.5 vs 68.1
- Traditional Chinese prose: 73.7 vs 59.7

One extra prompt asked for 25 near-identical JSON tool-call lines:

- ngram + MTP: 124.5 tokens/sec, draft 313/342 accepted
- ngram + DFlash 2: 109.1 tokens/sec, draft 295/312 accepted

Fixed format is faster than prose on both stacks. That is where ngram is supposed to show up. Chat benchmarks still understate agent-shaped output.

---

## 3. As an agent: QuixBugs

Same ReAct harness: read, write, run tests. 29 programs. The harness re-runs the tests. Test-file MD5 before and after.

- **ngram + MTP (24K):** **28 / 29**, 492 s, 171 tool calls, mean 105.2 tokens/sec in the loop. Miss: still `lis`. Malformed JSON 0. Cheats 0.
- **ngram + DFlash 2 (8K):** **24 / 29**, 783 s, 162 calls. Five misses: `find_first_in_sorted`, `kheapsort`, `lis`, `sqrt`, `subsequences`. JSON 0, cheats 0. Mean 78.0 tokens/sec.

The previous MTP-only 24K run was 27/29 in 589 s. This 28/29 in 492 s is one sample at temperature 0.7 — not "ngram repairs better." The numbers that hold are wall clock and generation speed inside the loop.

The 8K stack missed four more programs and took 291 extra seconds. The window is the cost.

Math with a Python tool (eight problems, answers brute-forced locally):

- ngram + MTP: 7/8, 254 s. Q2 (Pell equation) never emitted `ANSWER:`
- ngram + DFlash 2: 8/8, 310 s. Q2 passed this time

Q2 has failed on other configs too. Do not read a single temperature-0.7 run as "DFlash is better at math." For daily agent use, 24K is still the one that looks like a worker.

---

## 4. Takeaway

On this card, on this 3-bit file:

- ngram replays repeats. It is not a second model and not free context.
- **The larger window is ngram + MTP (24K).** ngram + DFlash 2 works at 8K.
- **The better agent is also ngram + MTP:** QuixBugs 28/29 vs 24/29, 492 s vs 783 s.
- Their 105K needs a thinner quant. Stacking ngram does not mint that window.

Daily driver: `./ops/qwen38.sh safe` or `safe-ngram`. To rerun this pair: `safe-ngram` and `dflash-ngram`.

Logs: https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU
Previous: https://medium.com/@aipruner1991/qwen-3-8-27b-real-test-5070ti-16gb-gpu-3d1414dd0564
