# I Retested the Viral DFlash2 105K Recipe on the Same 16GB Card

*Same 3-bit file. Same 5070 Ti. Same agent suite. The only swap is the draft model.*

---

In the last article I crushed Qwen3.8-27B to 3-bit and ran it on an RTX 5070 Ti 16GB: 27/29 QuixBugs, Tetris in ~35 seconds and actually playable, 8/8 hard math problems once I gave it a Python tool. That run used the model's built-in MTP (Multi-Token Prediction — guess the next batch of tokens in one shot).

Two days later someone on r/LocalLLaMA (BuffMcBigHuge) put DFlash 2 plus ngram-mod on a 4080 16GB and opened 105K context. The draft file is a public GGUF: `Qwen3.8-27B-DFlash2-Q4_K_M.gguf`.

I did not switch quants. Still `UD-Q3_K_XL` from the last article. The question is narrow: **the same DFlash 2 draft, on my fatter 3-bit file — what is left?**

Every number still came off this machine. Every math answer was brute-forced locally first.

Previous article: [3-bit real test](https://medium.com/@aipruner1991/qwen-3-8-27b-real-test-5070ti-16gb-gpu-3d1414dd0564). Code and raw logs: [GitHub](https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU).

---

## 0. Their recipe, not my file

Their target quant is `RVN-IQ3_XXS`, smaller than `UD-Q3_K_XL`, which is why 105K of KV cache fits. Roughly:

- `--spec-type draft-dflash,ngram-mod`
- `--spec-draft-n-max 5`
- `-c 105000`
- `-ctk q5_1 -ctv q5_1`
- draft GGUF on the GPU as well

I kept the target file on purpose. The last article's conclusions are glued to `UD-Q3_K_XL`; swapping it would be a different article. Sampling stays `temperature=0.7, top_p=0.8`, not their 1.0 / 0.95 / 20, so quality numbers stay comparable.

---

## 1. Stock llama.cpp will not load DFlash 2

The first failure is the file format, not speed.

`ghcr.io/ggml-org/llama.cpp:full-cuda` only understands DFlash **1**. A DFlash **2** GGUF dies with:

```
done_getting_tensors: wrong number of tensors; expected 81, got 58
```

You need llama.cpp [PR #27342](https://github.com/ggml-org/llama.cpp/pull/27342) (commit `5ecbe1a`). I built `local/llama.cpp:dflash2-cuda` with CUDA arch 120 for the 5070 Ti. The launcher now switches images per profile: `./ops/qwen38.sh dflash`.

The draft itself is small, about 1.14 GB, from `z-lab/Qwen3.8-27B-DFlash2-GGUF`.

---

## 2. 105K spills on this file

WSL2 does not report OOM. The server comes up, `/health` returns `ok`, the API answers — generation drops to 2–4 tokens/sec, or times out. Same failure mode as 4-bit in the last article, roughly 300× slower.

So I still use a 32-token probe and treat anything under 60 tokens/sec as spilled.

The Reddit n-max 5 / q5_1 / 16K–105K set **all spill** on `UD-Q3_K_XL`. The extra 1.1 GB draft plus n-max 5 compute buffers eat the VRAM that native MTP spent on a 24K window.

The working point that actually holds:

- context **8192**
- KV **q8_0**
- `--spec-draft-n-max 4`
- batch 256 / 128
- draft on the GPU
- ~15,069 MiB used, 927 MiB free
- 32-token probe at 68.2 tokens/sec

Parking the draft on CPU gets 16K back, at ~38 tokens/sec. Not worth it.

They opened 105K because the **target** was thinner. Not because DFlash 2 is magic.

---

## 3. At 8K vs 8K, DFlash 2 is not faster

Same PR build of llama.cpp, same 8K q8_0, same prompts (random salt in front so llama.cpp's prefix cache cannot inflate the numbers), ~600 tokens out, `reasoning_effort=low`.

**Generation speed (tokens/sec)**

- Python LRU: DFlash 2 **114.4**, MTP **110.0**
- HTML canvas: DFlash 2 **110.4**, MTP **121.6**
- English prose: DFlash 2 **81.3**, MTP **76.7**
- Traditional Chinese prose: DFlash 2 **62.7**, MTP **80.7**
- mean: DFlash 2 **92.2**, MTP **97.2**

DFlash 2 draft accept rates: code 458/528 (87%), HTML 77%, English prose 50%, Chinese prose 340/1031 (**33%**).

MTP was already better at fixed formats — last article: ~113 tokens/sec on tool calls, ~80 on Chinese prose. DFlash 2 is worse on Chinese prose because the draft guesses that shape poorly; a 33% accept rate is mostly wasted draft work.

On mean speed at this 8K point, DFlash 2 is within noise of native MTP. Chinese is slower. What you paid is context: 24K down to 8K.

---

## 4. The same quality suite

Launcher profile `dflash`. Same sampling as the last article.

### QuixBugs: 28 / 29

Last time 27 / 29, 589 s, 175 tool calls. This time **28 / 29, 738 s, 165 calls**. Malformed JSON 0. Test-file cheats 0.

The miss is still `lis` — it failed on MTP too. `subsequences` passed this time. Sampling is `temperature=0.7`; one run is not "DFlash 2 repairs better."

The useful number is generation speed inside the agent loop: **60.5 tokens/sec** this time, about 90–110 last time. Wall clock 589 s → 738 s. The files are small, so 8K is enough, but a fuller KV and a weaker draft accept rate make the loop slower.

### Tetris: 38 s average

All three finished. Feature checks 14/14. `node --check` **2/3** — run 3 died on `Unexpected token 'else'`. Last time: 3/3 playable, 35 s average. Generation speed 114–119 tokens/sec, in line with MTP on code. 8K is enough for a ~400-line HTML file. Syntax is not more reliable.

### Math: tools still win, 8K still clips

Same eight problems, same ground truth.

**Think only**

- MTP 24K: 4/8, 406 s, 43,015 tokens
- DFlash 2 8K: **3/8**, 451 s, 45,609 tokens
- All five misses are `got=None` at 8,000 output tokens. Not a wrong integer. It thought until the budget and never finished the sentence.

**Python tool**

- Last time: 8/8, 123 s, 25,754 tokens
- This time: **7/8**, 336 s, 30,280 tokens
- The miss is Q2 (smallest positive \(x\) for \(x^2 - 61y^2 = 1\)). 169 s, 6,959 output tokens, two tool calls, no `ANSWER:`. Thinking plus tool history filled 8K and got truncated.

"Sum of the digits of \(3^{1000}\)" with a tool: 7 seconds, correct (2142). Last time it was 2 seconds. Same order of magnitude. Tools still crush pure thinking.

The last article's conclusion still holds: for a local model, tools are cheaper than thinking time. This run adds a sentence: **the tool loop itself consumes context**. Cut the window from 24K to 8K and you clip the problem that thinks, calls, thinks again. Silence is still safer than a confident wrong answer — Q2 did not hand me a wrong 1.7 billion. It just never finished.

---

## 5. What I did not test

- I did **not** rerun 105K on their `RVN-IQ3_XXS`. Different file, different VRAM budget
- I did **not** make ngram-mod the default. llama.cpp's prefix cache makes unsalted ngram numbers look great. There is a `dflash-ngram` profile. The quality suite did not run on it
- I did **not** use the froggeric chat template
- I did **not** rerun the pelican-on-a-bicycle sweep. That data is 24K MTP

Their recipe can be true on a thinner quant. I am not disputing that post. I am disputing pasting those flags onto `UD-Q3_K_XL`.

---

## 6. Takeaway

On this card, on this 3-bit file, DFlash 2 is **not a speedup. It is a different draft paid for with context.**

At 8K vs 8K, mean generation speed matches native MTP; Chinese is slower. QuixBugs still repairs (28/29). Tetris still generates. Math with a tool drops from 8/8 to 7/8, and the drop is the window, not a dumber model.

Daily driver is still `./ops/qwen38.sh safe`: 24K, native MTP, no extra draft. DFlash 2 is worth trying if you switch to a thinner target quant that still has VRAM for the draft **and** a long context. That is what their article was doing. Not this one.

Full logs and launcher: https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU
