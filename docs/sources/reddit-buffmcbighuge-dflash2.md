---
title: "Large Context w/ MTP, DFlash2, ngram-mod, Testing Qwen3.8-27B on 16GB VRAM"
source: "https://www.reddit.com/r/LocalLLaMA/comments/1vt3cpw/large_context_w_mtp_dflash2_ngrammod_testing/"
author:
  - "[[BuffMcBigHuge]]"
published: 2026-08-20
created: 2026-08-21
description: "Not as technical as the other posts, my goal was to maximize context and performance (prefill/infer) on a 4080 16GB, for a local Hermes agen"
tags:
  - "clippings"
---
Not as technical as the other posts, my goal was to maximize context and performance (prefill/infer) on a 4080 16GB, for a local Hermes agent. Testing [RVN-IQ3\_XXS](https://huggingface.co/0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF), and [DFlash2 GGUF](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2-GGUF). I built llama.cpp locally in Windows with the dflash2 [branch](https://github.com/z-lab/llama.cpp-fork/tree/dflash2). Also using the [froggeric fix](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates/blob/main/chat_template.jinja).

First test, ngram-mod, 131072 context. Note that the TTFT on 128k may have been a fluke.

llama-server.exe --model "~\\.lmstudio\\models\\0bserverx\\Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF\\RVN-IQ3\_XXS.gguf" --chat-template-file "~\\froggeric\_fix\_qwen38.jinja" --chat-template-kwargs "{\\"preserve\_thinking\\":true, \\"reasoning\_effort\\":\\"medium\\"}" --alias default --jinja --spec-type ngram-mod --spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32 --threads 8 --fit off --n-gpu-layers 99 --ctx-size 131072 --batch-size 512 --ubatch-size 512 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.00 --presence-penalty 0 --repeat-penalty 1.0 --cache-type-k q5\_1 --cache-type-v q5\_1 --flash-attn on --sleep-idle-seconds 600 --parallel 1 --reasoning-format deepseek --reasoning-effort medium --reasoning-preserve --load-mode none![r/LocalLLaMA - Large Context w/ MTP, DFlash2, ngram-mod, Testing Qwen3.8-27B on 16GB VRAM](https://preview.redd.it/large-context-w-mtp-dflash2-ngram-mod-testing-qwen3-8-27b-v0-fe4e54op1fkh1.png?width=1080&crop=smart&auto=webp&s=19d566fa2b49eddc8b30d7c2225c4484a637334d)

Second test, DFlash2 + ngram-mod, 105000 context.

llama-server.exe --model "~\\.lmstudio\\models\\0bserverx\\Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF\\RVN-IQ3\_XXS.gguf" --model-draft "~\\Development\\Qwen3.8-27B-DFlash2-Q4\_K\_M.gguf" --chat-template-file "~\\Development\\froggeric\_fix\_qwen38.jinja" --chat-template-kwargs "{\\"preserve\_thinking\\":true, \\"reasoning\_effort\\":\\"medium\\"}" --alias default --jinja --spec-type draft-dflash,ngram-mod --spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32 --spec-draft-n-max 5 --threads 8 --fit off --n-gpu-layers 99 --n-gpu-layers-draft 99 --ctx-size 105000 --batch-size 512 --ubatch-size 512 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.00 --presence-penalty 0 --repeat-penalty 1.0 --cache-type-k q5\_1 --cache-type-v q5\_1 --flash-attn on --sleep-idle-seconds 600 --parallel 1 --reasoning-format deepseek --reasoning-effort medium --reasoning-preserve --load-mode none![r/LocalLLaMA - Large Context w/ MTP, DFlash2, ngram-mod, Testing Qwen3.8-27B on 16GB VRAM](https://preview.redd.it/large-context-w-mtp-dflash2-ngram-mod-testing-qwen3-8-27b-v0-jjhrsqo52fkh1.png?width=1080&crop=smart&auto=webp&s=0492e7b9b1bba7a959543df0dcdd749a19f28e44)

Finally, MTP, ngram-mod, 105000 context. I manually merged RVN-IQ3\_XXS with the MTP draft model instead of downloading the entire MTP merge via LMStudio.

llama-server.exe --model "~\\Development\\RVN-IQ3\_XXS-MTP.gguf" --chat-template-file "~\\froggeric\_fix\_qwen38.jinja" --chat-template-kwargs "{\\"preserve\_thinking\\":true, \\"reasoning\_effort\\":\\"medium\\"}" --alias default --jinja --spec-type draft-mtp,ngram-mod --spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32 --spec-draft-n-max 2 --threads 8 --fit off --n-gpu-layers 99 --n-gpu-layers-draft 99 --ctx-size 105000 --batch-size 512 --ubatch-size 512 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.00 --presence-penalty 0 --repeat-penalty 1.0 --cache-type-k q5\_1 --cache-type-v q5\_1 --flash-attn on --sleep-idle-seconds 600 --parallel 1 --reasoning-format deepseek --reasoning-effort medium --reasoning-preserve --load-mode none![r/LocalLLaMA - Large Context w/ MTP, DFlash2, ngram-mod, Testing Qwen3.8-27B on 16GB VRAM](https://preview.redd.it/large-context-w-mtp-dflash2-ngram-mod-testing-qwen3-8-27b-v0-oqc9m0th2fkh1.png?width=1080&crop=smart&auto=webp&s=42bf8dbc8980bf1ba81de4bb570e1f1147770e88)

Of I ran many more tests, these were the best results I had come across in valuing performance and speed. I defaulted to `--cache-type-k q5_1 --cache-type-v q5_1` for all tests, and did not quant the draft based on advice I've seen in this subreddit.

I did run IQ4\_XS with ngram-mod, but really maxed at 34000 context.

llama-server.exe --model "~/.lmstudio/models/0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF/RVN-IQ4\_XS.gguf" --chat-template-file "~\\Development\\froggeric\_fix\_qwen38.jinja" --chat-template-kwargs "{\\"preserve\_thinking\\":true, \\"reasoning\_effort\\":\\"medium\\"}" --alias default --jinja --spec-type ngram-mod --spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32 --threads 8 --fit off --n-gpu-layers 99 --ctx-size 34000 --batch-size 512 --ubatch-size 512 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.00 --presence-penalty 0 --repeat-penalty 1.0 --cache-type-k q5\_1 --cache-type-v q5\_1 --flash-attn on --sleep-idle-seconds 600 --parallel 1 --reasoning-format deepseek --reasoning-effort medium --reasoning-preserve --load-mode none![r/LocalLLaMA - Large Context w/ MTP, DFlash2, ngram-mod, Testing Qwen3.8-27B on 16GB VRAM](https://preview.redd.it/large-context-w-mtp-dflash2-ngram-mod-testing-qwen3-8-27b-v0-1g4cf0774fkh1.png?width=1080&crop=smart&auto=webp&s=f5383e23861475a11fd753248f0cab3f45434574)

For my purpose, I think MTP with 105000 is the way to go for now, unless you need the extra 25000k context for the harness, then ngram-mod is enough, albeit slower tok/s. Without MTP or DFlash2, I'd probably increase reasoning to xhigh to take advantage of more intelligence with larger thinking context if absolute performance isn't necessary.

I hope this helps anyone with 16GB. I'm sure you can run it faster, I'm open for feedback!

---

## Comments

> **chocofoxy** · [2026-08-20](https://reddit.com/r/LocalLLaMA/comments/1vt3cpw/comment/p4q7miw/) · 5 points
> 
> i found that the best is MTP + ngram
> 
> > **Embarrassed\_Soup\_279** · [2026-08-20](https://reddit.com/r/LocalLLaMA/comments/1vt3cpw/comment/p4qi8xn/) · 3 points
> > 
> > if you don't mind would you share your config?
> > 
> > > **Vancecookcobain** · [2026-08-20](https://reddit.com/r/LocalLLaMA/comments/1vt3cpw/comment/p4se0oy/) · 1 points
> > > 
> > > I guess he does

> **Then-Topic8766** · [2026-08-20](https://reddit.com/r/LocalLLaMA/comments/1vt3cpw/comment/p4s2t4g/) · 2 points
> 
> you have `--reasoning-preserve` already
> 
> you do not need `\"preserve_thinking\":true`

> **gpuz\_dev** · [2026-08-20](https://reddit.com/r/LocalLLaMA/comments/1vt3cpw/comment/p4q9vnh/) · 2 points
> 
> this is a really useful 16GB test. the crossover is the interesting part, dflash2 wins early but by 64k MTP is ~52.6 vs ~46.7 t/s, while ngram-only buys you another ~26k context. did the 105k MTP setup basically max the 16GB or was there any VRAM headroom left?
> 
> > **BuffMcBigHuge** · [2026-08-20](https://reddit.com/r/LocalLLaMA/comments/1vt3cpw/comment/p4qm5lm/) · 2 points
> > 
> > My goal was to max out my VRAM before prefill suffered. I can technically set 256k context on any setup and it runs, just abysmally.
> > 
> > > **gpuz\_dev** · [2026-08-20](https://reddit.com/r/LocalLLaMA/comments/1vt3cpw/comment/p4ry30x/) · 1 points
> > > 
> > > ah got it, so 105k is basically your practical performance limit rather than a hard OOM limit. that's actually an important distinction for 16GB setups

> **Dry\_Mortgage\_4646** · [2026-08-20](https://reddit.com/r/LocalLLaMA/comments/1vt3cpw/comment/p4qo6ri/) · 1 points
> 
> For my setup the winner is Dflash2