# ngram 不是第二顆模型。疊在 MTP 上，比疊在 DFlash 2 上更適合當 agent

*同一個 3-bit 檔、同一張 5070 Ti。比的是 ngram + MTP 對 ngram + DFlash 2：誰能開比較大、誰比較能修 bug。*

---

上一篇把 Qwen3.8-27B 壓到 3-bit，用模型自己的 MTP（Multi-Token Prediction，一次先猜下一批 token）跑完整套 agent 測試。後來 r/LocalLLaMA 有人在 16GB 卡上把 **ngram-mod** 分別疊在 MTP 和 DFlash 2 上，把 context 開到十萬。

我沒換量化檔，還是 `UD-Q3_K_XL`。這次只問三件事：ngram 是什麼、疊上去之後誰能開比較大、誰比較適合當 agent。

數字都是這台機器跑的。取樣維持 `temperature=0.7, top_p=0.8`。llama.cpp 同一份 PR #27342 編譯。

---

## 0. ngram-mod 在做什麼

它不是草稿模型。llama.cpp [PR #19164](https://github.com/ggml-org/llama.cpp/pull/19164) 在記憶體裡放一張約 400 萬格的雜湊表（大約 **16 MB RAM**，幾乎不佔 VRAM）。看到最近 N 個 token 以前出現過，就把「上次後面接什麼」提出來當草稿。主模型還是逐個驗收。

重複出現的形狀它猜得準：JSON 工具呼叫、差不多的 HTML、複製貼上的程式碼。沒見過的中文散文幾乎幫不上忙。

它可以跟神經草稿用逗號疊在同一個 `--spec-type` 裡：

- `draft-mtp,ngram-mod`
- `draft-dflash,ngram-mod`

MTP 和 DFlash 2 仍只能選一個。ngram 也**不會**讓 KV cache 變便宜。能開多大，還是看主檔肥不肥、旁邊有沒有多塞 1.1 GB 草稿。

Reddit 那組 lookup 我照抄：`--spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-ngram-mod-n-match 32`。

測速度時每題前面加隨機鹽。否則 llama.cpp 的 prefix cache 會讓第二次同一題看起來很快，那不是 ngram 的功勞。

---

## 1. 誰能開比較大：還是 MTP

32 個 token 的探針，低於每秒 60 個 token 當溢出。

**ngram + MTP**

- 8K / 16K / **24K** q8_0 都過（24K 探針 73.8 tokens/秒）
- 32K 溢出（0.1）

**ngram + DFlash 2**

- 8K / 12K / 16K q8_0 全部溢出（每秒 2 到 4 個 token）
- 16K q4_0 的 32 token 探針寫 60.8，看起來剛過線。拿去寫 600 個 token：**每秒 5.1 個**。探針會騙人。
- 真正站得住的工作點是 **8K、q4_0、n-max 3**。600 個 token 生成速度 92.0。

ngram 沒把窗口變大。MTP 還是 24K；DFlash 2 多一顆草稿，窗口更小。對方能開 105K，是目標量化更瘦。

---

## 2. 獨特輸出 vs 工具呼叫形狀

同一份編譯、prompt 有加鹽，各寫約 600 個 token：

**生成速度（tokens/秒）**

- 平均：ngram + MTP **94.6**，ngram + DFlash 2 **78.0**
- Python：103.8 vs 94.7
- HTML：120.5 vs 89.3
- 英文散文：80.5 vs 68.1
- 繁中散文：73.7 vs 59.7

另外出了一題「連續 25 行幾乎同款的 JSON 工具呼叫」：

- ngram + MTP：124.5 tokens/秒，草稿 313/342 過
- ngram + DFlash 2：109.1 tokens/秒，草稿 295/312 過

固定格式兩邊都比散文快。這就是 ngram 該出現的地方。拿聊天測速度，還是會低估它做 agent 的樣子。

---

## 3. 當 agent：修 bug 題庫

同一套 ReAct harness：讀檔、寫檔、跑測試。QuixBugs 29 題。成功判定是 harness 重跑測試，測試檔 MD5 前後比對。

- **ngram + MTP（24K）**：**28 / 29**，492 秒，171 次工具呼叫，迴圈裡平均生成速度 105.2 tokens/秒。失敗仍是 `lis`。格式錯誤 0，改測試 0。
- **ngram + DFlash 2（8K）**：**24 / 29**，783 秒，162 次。失敗五題：`find_first_in_sorted`、`kheapsort`、`lis`、`sqrt`、`subsequences`。格式錯誤 0，改測試 0。平均生成速度 78.0。

上一篇沒加 ngram 的 24K MTP 是 27/29、589 秒。這次 28/29、492 秒，取樣是 0.7，單次不能解釋成「ngram 讓它比較會修」。比較能講的是牆鐘時間和迴圈裡的生成速度。

8K 那組少修四題、慢了 291 秒。窗口不夠，工具迴圈比較容易卡住。

數學給 Python 工具（八道，答案本機先算過）：

- ngram + MTP：7/8，254 秒。Q2（Pell 方程）沒吐 `ANSWER:`
- ngram + DFlash 2：8/8，310 秒。Q2 這次過了

Q2 兩邊都曾在別的設定裡掛過，temperature 0.7 單次不要寫成「DFlash 比較會算」。整體還是 24K 那組比較像能當日常 agent 的東西。

---

## 4. 結論

在這張卡、這個 3-bit 檔上：

- ngram 是「看見重複就猜」，不是第二顆模型，也不是免費 context。
- **能開比較大的是 ngram + MTP（24K）**。ngram + DFlash 2 工作點是 8K。
- **比較適合 agent 的也是 ngram + MTP**：QuixBugs 28/29 對 24/29，492 秒對 783 秒。
- 對方那篇的 105K，換檔才有機會，不是把 ngram 疊上去就會變出來。

日常我開 `./ops/qwen38.sh safe` 或 `safe-ngram`。要重跑這組對照：`safe-ngram` 和 `dflash-ngram`。

完整 log：https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU
上一篇：https://medium.com/@aipruner1991/qwen3-8-27b%E5%AF%A6%E6%B8%AC-5070ti-16gb-gpu-e72cddbb78e1
