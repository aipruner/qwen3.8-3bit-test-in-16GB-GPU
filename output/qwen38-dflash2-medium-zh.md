# 網路上那套 DFlash2 + 105K 配方，我拿同一張 16GB 卡實測了一遍

*同一個 3-bit 檔、同一張 5070 Ti、同一套 agent 題庫。換的是草稿模型，不是顯卡。*

---

上一篇我把 Qwen3.8-27B 壓到 3-bit，在 RTX 5070 Ti 16GB 上跑完整套測試：QuixBugs 29 題修 27 題、俄羅斯方塊 35 秒能玩、數學給 Python 工具之後 8 題全對。那次用的是模型自己內建的 MTP（Multi-Token Prediction，一次先猜下一批 token）。

兩天後 r/LocalLLaMA 有人（BuffMcBigHuge）在 4080 16GB 上，用 DFlash 2 草稿加上 ngram-mod，把 context 開到 105K。草稿檔就是現成的 `Qwen3.8-27B-DFlash2-Q4_K_M.gguf`。

我沒換量化檔。還是上一篇那個 `UD-Q3_K_XL`。問題很單純：**同一套 DFlash 2，換到我這個比較肥的 3-bit 檔上，還剩什麼？**

所有數字仍是這台機器自己跑的。數學題標準答案還是本機暴力法先算過。

上一篇：[3-bit 實測](https://medium.com/@aipruner1991/qwen3-8-27b%E5%AF%A6%E6%B8%AC-5070ti-16gb-gpu-e72cddbb78e1)。程式碼與原始 log：[GitHub](https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU)。

---

## 0. 他們的配方，不是我的檔

對方用的目標量化是 `RVN-IQ3_XXS`，比我的 `UD-Q3_K_XL` 更小，所以 VRAM 才擠得出 105K KV cache。啟動參數大意是：

- `--spec-type draft-dflash,ngram-mod`
- `--spec-draft-n-max 5`
- `-c 105000`
- `-ctk q5_1 -ctv q5_1`
- 草稿 `Qwen3.8-27B-DFlash2-Q4_K_M.gguf` 也放 GPU

我刻意不換目標檔。上一篇的結論全部綁在 `UD-Q3_K_XL` 上，換檔就變成另一篇文章。取樣也維持 `temperature=0.7, top_p=0.8`，不跟他們的 1.0 / 0.95 / 20 混在一起，品質數字才能跟上一篇比。

---

## 1. 現成的 llama.cpp 載不進 DFlash 2

第一個坑不是速度，是檔案格式。

Docker Hub 上的 `ghcr.io/ggml-org/llama.cpp:full-cuda` 只認得 DFlash **1**。DFlash **2** 的 GGUF 丟進去會直接失敗：

```
done_getting_tensors: wrong number of tensors; expected 81, got 58
```

要 llama.cpp [PR #27342](https://github.com/ggml-org/llama.cpp/pull/27342)（commit `5ecbe1a`）。我在這台機器編了一份 `local/llama.cpp:dflash2-cuda`，CUDA arch 120，5070 Ti 才跑得動。啟動器現在會依 profile 自動換 image，指令是 `./ops/qwen38.sh dflash`。

草稿檔本身很小，約 1.14 GB，Hugging Face 上 `z-lab/Qwen3.8-27B-DFlash2-GGUF` 就能抓。

---

## 2. 105K 在我這個檔上會溢出

WSL2 不報 OOM。服務會起來，`/health` 回 `ok`，API 也會答 —— 生成速度掉到每秒 2 到 4 個 token，或直接 timeout。上一篇測 4-bit 就是這個樣子，差約 300 倍。

所以我還是用 32 個 token 的探針，低於每秒 60 個 token 就當溢出。

Reddit 那組 n-max 5、q5_1、16K 到 105K，在 `UD-Q3_K_XL` 上全部溢出。多出來的 1.1 GB 草稿，加上 n-max 5 的計算緩衝，把 MTP 拿去開 24K context 的 VRAM 吃光了。

真正站得住的工作點：

- context **8192**
- KV **q8_0**
- `--spec-draft-n-max 4`
- batch 256 / 128
- 草稿也放 GPU
- 占用約 15,069 MiB，剩 927 MiB
- 32 token 探針生成速度 68.2 tokens/秒

把草稿丟 CPU 可以塞回 16K，但生成速度只剩約 38 tokens/秒，划不來。

對方能開 105K，是因為目標量化比較小。不是 DFlash 2 魔法，是檔案比較瘦。

---

## 3. 8K 對 8K，DFlash 2 沒有比較快

同一份 PR 編譯的 llama.cpp、同一個 8K q8_0、同一組 prompt（每題前面加隨機鹽，避免 llama.cpp 的 prefix cache 把數字灌水），各寫約 600 個 token，`reasoning_effort=low`。

**生成速度（tokens/秒）**

- Python LRU：DFlash 2 **114.4**，MTP **110.0**
- HTML canvas：DFlash 2 **110.4**，MTP **121.6**
- 英文散文：DFlash 2 **81.3**，MTP **76.7**
- 繁中散文：DFlash 2 **62.7**，MTP **80.7**
- 平均：DFlash 2 **92.2**，MTP **97.2**

DFlash 2 的草稿接受率：程式碼 458/528（87%）、HTML 77%、英文散文 50%、中文散文 340/1031（**33%**）。

MTP 猜固定格式本來就準，上一篇寫過：產工具呼叫每秒 113 個 token，寫中文散文只剩 80。DFlash 2 在中文散文上更差，因為草稿模型對這種輸出猜不準，接受率掉到三成，等於白猜。

平均來看，8K 這個工作點上 DFlash 2 跟原生 MTP 在誤差範圍內。中文更慢。你付出的是 context：24K 變成 8K。

---

## 4. 同一套品質測試

啟動器 profile 是 `dflash`。取樣跟上一篇相同。

### QuixBugs：28 / 29

上一篇 27 / 29，589 秒，175 次工具呼叫。這次 **28 / 29，738 秒，165 次**。格式錯誤 0，改測試作弊 0。

失敗的還是 `lis`：上一篇也沒修過。`subsequences` 這次過了 —— 取樣是 `temperature=0.7`，單次不能解釋成「DFlash 2 比較會修 bug」。

比較有用的數字是修 bug 迴圈裡的平均生成速度：這次 **60.5 tokens/秒**，上一篇大約 90 到 110。總時間 589 秒變成 738 秒。檔案很小，8K 夠用，但 KV 比較滿、草稿接受率比較差，牆鐘時間變長。

### 俄羅斯方塊：平均 38 秒

三次都跑完，功能檢查 14/14。`node --check` **2/3**，第三次卡在 `Unexpected token 'else'`。上一篇是 3/3 能玩、平均 35 秒。生成速度 114 到 119 tokens/秒，跟 MTP 寫程式差不多。8K 寫一個 400 行的 HTML 夠用，語法沒有比較穩。

### 數學：給工具還是比較划算，但 8K 會切到題

八道題，標準答案沒變。

**只讓它自己想**

- 上一篇 MTP 24K：對 4 題，406 秒，43,015 個 token
- 這次 DFlash 2 8K：對 **3** 題，451 秒，45,609 個 token
- 錯的五題全部是 `got=None`，輸出頂到 8,000 個 token。不是講錯數字，是想完沒講完

**給一個能跑 Python 的工具**

- 上一篇：對 8 題，123 秒，25,754 個 token
- 這次：對 **7** 題，336 秒，30,280 個 token
- 唯一失敗是 Q2（Pell 方程 \(x^2 - 61y^2 = 1\) 的最小正整數 \(x\)）。想了 169 秒、輸出 6,959 個 token、呼叫工具兩次，沒吐出 `ANSWER:`。8K context 被思考加工具紀錄填滿，被截斷了

「3 的 1000 次方，各位數字加起來是多少」這次給工具 7 秒就對（答案 2142）。上一篇是 2 秒。數量級沒變，還是工具碾推理。

上一篇的結論仍然成立：給工具比給思考時間划算。這次多了一句：**工具迴圈本身也要吃 context**。你把窗口從 24K 砍到 8K，就會在 Pell 這種會東想西想再呼叫工具的題上截斷。沉默還是比講錯安全 —— Q2 沒給我一個錯的 17 億，它是沒講完。

---

## 5. 我沒測什麼

- **沒有**用對方的 `RVN-IQ3_XXS` 重跑 105K。那是另一個量化檔，VRAM 帳不一樣
- **沒有**把 ngram-mod 當成預設。llama.cpp 的 prefix cache 會讓沒加鹽的 ngram 數字看起來很美。啟動器裡有 `dflash-ngram` profile，品質套件沒跑過
- **沒有**用 froggeric 的 chat template
- **沒有**重跑上一篇那題騎腳踏車的鵜鶘。那是 24K MTP 的數據

對方的配方在更小的量化檔上可以成立。我沒否認那篇。我否認的是：把那組參數原封不動貼到 `UD-Q3_K_XL` 上。

---

## 6. 結論

DFlash 2 在我這張卡、這個 3-bit 檔上，**不是加速器，是用 context 換來的另一種草稿**。

8K 對 8K，平均生成速度跟原生 MTP 差不多，中文更慢。QuixBugs 還能修（28/29），俄羅斯方塊還能生，數學給工具從 8/8 掉到 7/8，掉在窗口不夠而不是模型突然變笨。

日常我還是開 `./ops/qwen38.sh safe`：24K、原生 MTP、不需要額外草稿。DFlash 2 值得試的條件是 —— 你願意換更瘦的目標量化，VRAM 同時塞得下草稿**和**長 context。那是對方那篇文章在做的事。不是我這篇。

完整 log 與啟動器：https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU
