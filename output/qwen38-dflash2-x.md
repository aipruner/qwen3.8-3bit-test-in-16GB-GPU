# X — one Premium post (English)

Copy everything below the line into a single X Premium post.

---

Follow-up to the 3-bit Qwen3.8-27B test on a 5070 Ti 16GB.

Someone on r/LocalLLaMA ran DFlash 2 + ngram-mod on a 4080 16GB and opened 105K context. Public draft GGUF, ~1.1 GB. I kept my file: same UD-Q3_K_XL, same card class, same harness.

Stock llama.cpp will not load DFlash 2. expected 81 tensors, got 58. You need PR #27342.

Their n-max 5 / q5_1 / 105K flags spill on this quant. Server still starts. /health still says ok. Generation drops to 2–4 tok/s. WSL2 does not report OOM.

Working point that actually holds: 8K, q8_0, n-max 4. ~15,069 MiB used. They got 105K because the target quant was thinner, not because DFlash 2 is magic.

Fair 8K-vs-8K specspeed, cache-busted, same llama.cpp build:

Python 114 vs 110. HTML 110 vs 122. English prose 81 vs 77. Chinese prose 63 vs 81. Mean 92 vs 97 tok/s.

Chinese draft accept rate: 33%. MTP was already better at fixed formats. DFlash 2 does not win that bet on this file.

Same quality suite:

QuixBugs 28/29 vs 27/29 last time. 738s vs 589s. 165 tool calls. Format never broke. Never cheated the tests. lis failed both times.

Tetris ~38s avg vs 35s. Feature checks 14/14. node --check 2/3 (one Unexpected token else).

8 math problems, answers brute-forced locally first.

Think only: 3/8. 451s. All five misses were "thought until the budget, never finished."

Python tool: 7/8. 336s. Last time 8/8 in 123s. The miss is the Pell equation. 169s, two tool calls, no ANSWER. 8K filled up. Truncated.

Tools are still cheaper than thinking time. New sentence: the tool loop consumes context too. Cut the window from 24K to 8K and you clip the problem that thinks, calls, thinks again.

Daily driver stays 24K native MTP. DFlash 2 is worth it if you switch to a thinner target that still has VRAM for the draft and a long context. That is what their post was doing. Not this file.

Code + logs: github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU
Previous: https://medium.com/@aipruner1991/qwen-3-8-27b-real-test-5070ti-16gb-gpu-3d1414dd0564

#Qwen38 #LocalLLM
