# Threads — ngram + MTP vs ngram + DFlash 2（3 則）

---

## Post 1 — ngram 不是第二顆模型

Reddit 有人在 16GB 卡上把 ngram-mod 疊在 MTP 或 DFlash 2 上，context 開到十萬。

ngram-mod 不是草稿模型。llama.cpp 在記憶體裡放一張約 400 萬格的雜湊表，大約 16 MB RAM，幾乎不佔 VRAM。最近 N 個 token 以前出現過，就把上次後面接的提出來。主模型還是要驗收。

JSON 工具呼叫這種重複形狀它猜得準。沒見過的中文散文幾乎幫不上。

它可以跟 MTP 或 DFlash 2 用逗號疊在一起，但這兩種神經草稿還是只能選一個。ngram 也不會讓 KV cache 變便宜。

我沒換量化。還是上一篇的 UD-Q3_K_XL。Lookup 尺寸照抄對方：n-min 4、n-max 8、n-match 32。

---

## Post 2 — 能開比較大的還是 ngram + MTP

同一份 llama.cpp，探針低於每秒 60 個 token 當溢出。

ngram + MTP：8K / 16K / 24K q8_0 都過，32K 溢出。工作點 24K。

ngram + DFlash 2：q8_0 從 8K 到 16K 全溢出。16K q4_0 的 32 token 探針寫 60.8，拿去寫 600 個 token 掉到每秒 5.1 個。探針會騙人。真正站得住的是 8K、q4_0、n-max 3，600 token 生成速度 92。

ngram 沒把窗口變大。對方 105K 是目標檔比較瘦。

加鹽的 600 token 平均生成速度：ngram + MTP 94.6，ngram + DFlash 2 78.0。繁中散文 73.7 vs 59.7。出 25 行同款 JSON 工具呼叫：124.5 vs 109.1。固定格式兩邊都比散文快。

---

## Post 3 — 當 agent，也是 ngram + MTP

同一套讀檔寫檔跑測試。QuixBugs 29 題。

ngram + MTP（24K）：28/29，492 秒，171 次工具呼叫，迴圈裡平均 105.2 tokens/秒。失敗仍是 lis。格式 0 錯，0 次改測試。

ngram + DFlash 2（8K）：24/29，783 秒。多掛四題。平均 78.0。格式 0 錯，0 次改測試。

上一篇沒加 ngram 的 MTP 是 27/29、589 秒。28 對 27 是 temperature 0.7 單次，不要寫成 ngram 比較會修。能講的是 24K 比較快、8K 比較容易卡住。

數學給 Python 工具：MTP 那組 7/8（Pell 沒講完），DFlash 那組 8/8 但多花時間。單次不要倒過來當結論。

日常我開 24K 的 safe 或 safe-ngram。

完整數據：https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU
#Qwen38 #LocalLLM
