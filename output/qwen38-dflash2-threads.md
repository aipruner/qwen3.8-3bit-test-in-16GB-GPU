# Threads — DFlash2 實測（3 則）

上一篇 Threads 是 24K 原生 MTP。這三則是 2026-08-21 用同一個 3-bit 檔重跑 DFlash 2 之後的數字。不要跟上一篇的 27/29、8/8 混在同一則裡講成「又測了一次更快」。

---

## Post 1 — 105K 那組旗標，換到我的檔會溢出

上一篇我用 5070 Ti 16GB 跑 Qwen3.8-27B 的 3-bit（UD-Q3_K_XL），靠模型自己的 MTP。

兩天後 Reddit 有人在 4080 16GB 上用 DFlash 2 草稿把 context 開到 105K。草稿檔是現成的，約 1.1 GB。

我沒換量化。還是那個 3-bit 檔。

現成的 llama.cpp 載不進 DFlash 2：expected 81 tensors, got 58。要自己編 PR #27342。

編完之後，對方那組 n-max 5、q5_1、105K，在我這個檔上會溢出。服務還是會起來，生成速度掉到每秒 2 到 4 個 token。WSL2 不報 OOM，/health 照樣回 ok。

真正站得住的工作點是 8K、q8_0、n-max 4。VRAM 約 15,069 MiB。對方能開 105K，是因為目標量化比較瘦，不是 DFlash 2 魔法。

---

## Post 2 — 8K 對 8K，沒有比較快

同一份編譯、同一個 8K、同一組 prompt（有加隨機鹽，避免 cache 灌水），各寫約 600 個 token。

生成速度（tokens/秒）：

- Python：DFlash 2 114.4，MTP 110.0
- HTML：110.4 vs 121.6
- 英文散文：81.3 vs 76.7
- 繁中散文：62.7 vs 80.7
- 平均：92.2 vs 97.2

中文散文的草稿接受率只有 33%。MTP 猜固定格式本來就準，上一篇寫過工具呼叫 113、中文散文 80。DFlash 2 在中文上更差。

你付出的是 context：24K 變成 8K。平均速度在誤差範圍內。

---

## Post 3 — 同一套題庫：修 bug 還能修，數學被 8K 切到

同一套 harness，取樣沒改。

QuixBugs：28/29，738 秒，165 次工具呼叫，格式 0 錯，0 次改測試。上一篇是 27/29、589 秒。失敗的還是 lis。subsequences 這次過了，temperature 0.7 單次不能當成「比較會修」。修 bug 迴圈裡平均生成速度 60.5，上一篇約 100。

俄羅斯方塊平均 38 秒（上一篇 35），三次功能檢查都過，node --check 2/3，有一次 else 語法錯。

數學八道，答案還是本機先算過：

- 只讓它想：3/8，451 秒。五題失敗全部是想完沒講完。
- 給 Python 工具：7/8，336 秒。上一篇 8/8、123 秒。掛掉的是 Pell 方程，169 秒、兩次工具，沒吐 ANSWER。8K 被思考加工具紀錄填滿。

給工具還是比給思考時間划算。這次多一句：工具迴圈也要吃 context。砍窗口會切到會東想西想的題。

日常我還是開 24K 原生 MTP。DFlash 2 值得試的條件是你換更瘦的目標量化，VRAM 同時塞得下草稿和長 context。

完整數據與程式碼：https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU
上一篇 Medium：https://medium.com/@aipruner1991/qwen3-8-27b%E5%AF%A6%E6%B8%AC-5070ti-16gb-gpu-e72cddbb78e1
#Qwen38 #LocalLLM
