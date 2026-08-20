# X — ngram + MTP vs ngram + DFlash 2

Copy everything below the line into a single X Premium post.

---

Follow-up. Same 3-bit Qwen3.8-27B file. Same 5070 Ti 16GB. This time I stacked ngram-mod the way the r/LocalLLaMA 105K post did — on MTP, and on DFlash 2 — and asked which window is larger and which one acts like an agent.

ngram-mod is not a second model. llama.cpp keeps a ~4M-slot hash table of recent token n-grams. About 16 MB RAM. Almost no VRAM. If the last N tokens have been seen, it proposes what followed last time. The target still verifies.

It helps repeated shapes: JSON tool calls. Unique Chinese prose: almost nothing. It stacks with MTP or DFlash 2 via a comma. You still pick one neural draft. It does not cheapen KV cache.

ngram + MTP: 24K q8_0 holds. 32K spills.

ngram + DFlash 2: 8K–16K q8_0 all spill. A 16K q4_0 32-token probe said 60.8 tok/s. A 600-token write: 5.1. The probe lies. Working point that actually held: 8K, q4_0, n-max 3, 92.0 tok/s on 600 tokens.

ngram did not grow the window. Their 105K used a thinner quant.

Salted 600-token mean: ngram+MTP 94.6 vs ngram+DFlash2 78.0. Chinese prose 73.7 vs 59.7. 25 lines of lookalike JSON tool calls: 124.5 vs 109.1.

QuixBugs, same ReAct harness:

ngram+MTP 24K: 28/29. 492s. 171 tool calls. Mean 105.2 tok/s in the loop. Miss: lis. Format never broke. Never cheated.

ngram+DFlash2 8K: 24/29. 783s. Four extra misses. Mean 78.0.

Previous MTP-only run was 27/29 in 589s. Don't spin 28 vs 27 as "ngram repairs better." Temperature 0.7, one sample. The 8K window is what costs four programs and 291 extra seconds.

Daily driver stays 24K: safe or safe-ngram.

Code + logs: github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU

#Qwen38 #LocalLLM
