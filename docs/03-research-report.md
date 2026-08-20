# 03 — 研究報告：Qwen3.8-27B 與 2026-08 前沿模型

*完成日期：2026-08-19 · 來源：14 個 · 證據等級標注見文末*

---

## 執行摘要

Qwen3.8-27B 是 2026-08-14 釋出的 27B dense vision-language model，Apache 2.0。
它的重要性不在於「最強」，而在於**它是能塞進單張消費級顯卡的最強模型** ——
一個 13 GB 的檔案在 coding benchmark 上與前沿 API 互有勝負。

三個要點：

1. **架構沒變，變的是訓練。** config 與 Qwen3.6-27B 幾乎相同，
   GGUF 的 `general.architecture` 直接標成 `qwen35`。這對本地部署是好消息 ——
   既有 runtime 不需要新的 operator stack 就能 day-zero 支援。
2. **官方 benchmark 全是 vendor-reported，截至 2026-08 中旬沒有獨立複現。**
   Artificial Analysis 也還沒發布 27B 的 intelligence index。
3. **量化品質的損失比多數人以為的小得多。** 受控研究顯示 4-bit 以上與 BF16
   的差異在雜訊範圍內。真正的懸崖在 2-bit，以及 3-bit 內部的 KL divergence 差異。

---

## 1. Qwen3.8-27B 是什麼

### 規格

| 項目 | 值 |
|---|---|
| 參數量 | 27B dense（runtime 實測 27.32B） |
| Layers | 64 |
| Layer layout | 16 × ( 3× (Gated DeltaNet → FFN) → 1× (Gated Attention → FFN) ) |
| Full attention | 24 Q heads / 4 KV heads / head_dim 256 |
| Linear attention | 48 V heads / 16 QK heads / head_dim 128 |
| Context | 262,144 native，YaRN 可到 1,000,000 |
| Vision | 原生 image + video，vision encoder 27 層 |
| MTP | 有，multi-step 訓練的 nextn head |
| License | Apache 2.0 |

### 架構的關鍵：3:1 的 hybrid attention

64 層裡 **48 層是 Gated DeltaNet（linear attention）、16 層是 full Gated Attention**。
Gated DeltaNet 的狀態是**固定大小的 recurrent state**，不隨 context 成長；
**只有那 16 層需要 KV cache**。

```
16 layers × 4 KV heads × 256 head_dim × 2 (K+V) × 2 bytes = 65,536 bytes = 64 KB/token
```

約是傳統 64 層 dense model 的四分之一。這是 27B 模型敢宣稱 262K native context 的原因。

**但這個設計有代價**，而且這個代價在 16 GB 卡上是決定性的 ——
recurrent state 每個 token 都要跨裝置同步，
所以 **CPU offload 的懲罰遠比一般 dense model 嚴重**（實測 1 層 = −60%）。
詳見 [04-benchmarks.md](04-benchmarks.md)。

---

## 2. 對比前沿模型

### 2.1 對比閉源前沿

⚠️ **以下全部是 vendor-reported**，Qwen 自己跑的。部分 benchmark 是 in-house、
部分修正過 ground truth、競爭對手分數是 import 而非重跑。

| | Qwen3.8-27B | Qwen3.6-27B | Opus4.6 Max |
|---|---|---|---|
| SWE-bench Pro | **61.7** | 53.5 | 53.4 |
| QwenSWEBench (in-house) | **79.0** | 49.3 | 63.8 |
| LiveCodeBench v6 | **90.3** | 83.9 | 88.8 |
| OSWorld-Verified | **84.3** | 63.9 | 72.7 |
| DeepSWE 1.1 | **42.2** | 13.3 | — |
| Terminal Bench 2.1 | 73.0 | 63.4 | **78.2** |
| NL2Repo-Bench | 42.3 | 36.2 | **47.6** |
| GPQA Diamond | 89.2 | 87.8 | **91.3** |
| HLE | 30.8 | 24.0 | **40.0** |

**它贏一些 row、輸一些 row，而計分板是廠商自己做的。**
「beats Opus」是標題不是結論。真正的故事已經夠驚人：
一個免費下載的 28B 檔案在 coding benchmark 上與前沿 API 互有勝負。

社群最強的反面意見值得記錄：
> "They do not beat opus on real-world usage... Qwen models are good, but no."
> 回應：「那我們就需要能清楚顯示這件事的有意義 benchmark，否則都是揮手。」

### 2.2 對比開源前沿（第三方榜，2026-08）

這些是**跑不動在消費硬體上**的大模型：

| 模型 | 規模 | HLE | GPQA-D | SWE-bench | Terminal-Bench 2.1 | Context |
|---|---|---|---|---|---|---|
| Kimi K3 | 2.8T / 104B active | **56%** | **93.5%** | — | **88.3%** | 1M |
| GLM 5.2 | — | 54.7% | 91.2% | — | 81.0% | 128K |
| DeepSeek V4 Pro | — | 48.2% | 90.1% | **80.6%** | — | 384K |
| MiniMax M3 | — | — | 93.0% | 80.5% | 66.0% | 512K |
| **Qwen3.8-27B** | **27B dense** | 30.8%\* | 89.2%\* | 61.7%\* (Pro) | 73.0%\* | 262K |

\* vendor-reported。SWE-bench Pro ≠ SWE-bench Verified，數字不可直接比較。

**位置很清楚**：GPQA-Diamond 89.2 對比 Kimi K3 的 93.5 只差 4 個百分點，
但一個要 2.8T 參數的叢集，一個是 13 GB 的檔案。

### 2.3 對比同級 dense（能在單卡跑的）

第三方在單張 RTX 4090（24 GB）上的同條件測試：

| 項目 | 勝者 | 數據 |
|---|---|---|
| Coding agent / repo 編輯 | **Qwen3.8** | 12/12 pass@1；35/36 seeded runs |
| 固定 token 預算下的推理 | **Qwen3.8** | 39/40 pass@3 |
| 私有文件 QA | **Qwen3.8** | 23/24（Gemma 4 31B 是 22/24） |
| 嚴格的 declared tool call | **Gemma 4 31B-it** | 90/90 single、30/30 multi-step |
| Vision | **Gemma 4 31B-it** | 19/20（Qwen3.8 18/20） |
| 寫作 / 潤稿 | 平手 | 94/96 vs 93/96 vs 93/96 |
| Decode 速度 | 平手 | 兩個 Qwen 都約 49 t/s；Gemma 慢 8.3% |

另一組獨立測試（tool-eval-bench，69 scenarios）比較 3.6 → 3.8：

| | Qwen3.6-27B | Qwen3.8-27B |
|---|---|---|
| Overall | 88/100 | 91/100 |
| Multi-step chains | 75% | **100%** |
| Autonomous planning | 67% | **100%** |
| Structured reasoning | 83% | **100%** |
| Error recovery | 50% | 67% |

**進步的形狀是「同樣的速度、更好的判斷」，不是「更快」。**
overall 只從 88 到 91，但增益全部集中在困難的 agentic 類別。

---

## 3. 量化評比：不同壓縮程度表現如何

### 3.1 最好的公開證據

Quesma（Piotr Migdał, 2026-07-27）對**同架構的 Qwen3.6-27B** 做了完整量化階梯的
受控測試。成本：本機 37 小時 + 390 萬 token，雲端 GPU $1,430。
這是目前最嚴謹的公開研究。

**結論比多數人預期的溫和得多：**

```
BF16 ─── Q8 ─── Q6 ─── Q5 ─── Q4 ┊ Q3 ┊ Q2
└──── 差異在雜訊範圍內 ────┘  邊緣  真的輸
```

| 測試 | 結果 |
|---|---|
| Pelican SVG 盲測（5 隻/量化，pairwise duel，Bradley-Terry 計分） | BF16 → 4-bit 排名純屬雜訊，評審分不出來。2-bit 真的輸（UD-IQ2_XXS 約 20 場輸 19 場） |
| Terminal-Bench 2.1 (n=89) | 預期看到懸崖，實際是雜訊 |
| AIME-120 | 4-bit 以上都貼近完整模型。**Q3_K_M 73.3% vs Q3_K_S 54.2%** |
| Top-1 agreement vs BF16 | Q8_0 = 99.3% |

### 3.2 最重要的那條規則

> **比檔案大小更能預測品質的是 KL divergence。**
> KLD < 0.05 的量化表現接近 BF16；KLD > 0.08 的就掉下去。

這解釋了為什麼同樣是 3-bit，`Q3_K_M`（73.3%）和 `Q3_K_S`（54.2%）差這麼多，
也解釋了為什麼 Unsloth Dynamic（`UD-` 前綴，依張量敏感度不均勻分配 bit）
在同體積下更好。

社群獨立量測的誠實參考值：**UD-Q6 → UD-Q3 之間，各種 eval 掉 0–5%。**

### 3.3 一個必須記住的但書

上述證據**幾乎都是單輪任務**。有一派意見認為 agentic 工作的量化容忍度低得多，
理由是複利：

| 每步可靠度 | 15 步 trajectory 端到端成功率 |
|---|---|
| 99% | 86% |
| 97% | **63%** |

單輪測驗上像雜訊的 2 個百分點，在任務完成率上是 23 個百分點。

**這個推論在數學上無懈可擊，但前提（「量化讓每步掉 2%」）本身沒有被公開測量過。**
反例也存在：OVERBRING Labs 用 `UD-Q4_K_XL` 加上 `-ctv q4_0`
完成了跨三 repo 的自主除錯任務，沒有 doom loop。

實務上這應該被當成「在 agentic 場景調高保守度的理由」，而非已驗證的數字。
本機的做法是：權重接受 3-bit（有受控證據），
但 **KV cache 堅持用 q8_0**（KV 量化的品質風險有具體案例，證據比權重量化更強）。

### 3.4 完整量化階梯

`unsloth/Qwen3.8-27B-GGUF`（2026-08-19 抓取，共 22 個檔）：

| 檔案 | GB | GiB | 適用 VRAM | 評價 |
|---|---|---|---|---|
| BF16 | 54.66 | 50.9 | 64 GB+ | 參考基準 |
| UD-Q8_K_XL | 31.46 | 29.3 | 48 GB | GGUF 最高保真 |
| Q8_0 | 29.05 | 27.1 | 48 GB | Top-1 99.3% vs BF16 |
| UD-Q6_K_XL | 25.92 | 24.1 | 36–48 GB | |
| Q6_K | 22.88 | 21.3 | 32 GB | 32 GB 卡的高保真選擇 |
| UD-Q5_K_XL | 20.22 | 18.8 | 32 GB | |
| Q5_K_M | 19.83 | 18.5 | 24–32 GB | |
| **UD-Q4_K_XL** | 17.92 | 16.7 | 24–32 GB | **24 GB 卡的最佳預設** |
| Q4_K_M | 17.11 | 15.9 | 24 GB | 相容性最好的 4-bit baseline |
| IQ4_XS | 15.71 | 14.6 | 20 GB+ | 最小的「還算 4-bit」 |
| Q3_K_M | 13.82 | 12.9 | 16 GB（勉強） | AIME 73.3% |
| **UD-Q3_K_XL** | 13.44 | 12.5 | **16 GB** | **本機的選擇** |
| Q3_K_S | 12.57 | 11.7 | 16 GB | ⚠️ **AIME 54.2%，避開** |
| UD-IQ3_XXS | 11.91 | 11.1 | 14 GB | 12 GB 卡的選項 |
| UD-Q2_K_XL | 10.68 | 9.9 | 12–16 GB | 明顯品質損失 |
| UD-IQ2_XXS | 9.01 | 8.4 | 12 GB | 盲測中約 20 場輸 19 場 |
| mmproj-F16 | 0.93 | 0.87 | +0.87 GiB | vision 用，需另外下載 |

### 3.5 「Q4」不是一個身分

同一個模型、同名量化，不同 publisher 差 13%：

| Publisher | `Qwen3.8-27B-Q4_K_M.gguf` |
|---|---|
| LM Studio | 16.81 GB |
| Unsloth | 17.11 GB |
| Bartowski | 17.77 GB |
| ggml-org | 18.97 GB |

差異來自轉換用的 llama.cpp build、imatrix calibration corpus、
embedding/output head 是否保持高精度、**MTP head 是內嵌還是拆檔**、
以及有沒有附 vision projector。

**推薦一個 GGUF 時要講 repo + revision + 檔名，只說「Q4」不可重現。**

---

## 4. 實務上的三個地雷

### 4.1 `xhigh` 預設的過度思考

模型預設 `reasoning_effort: xhigh`。Simon Willison 的實測：

- 「畫一隻騎腳踏車的 pelican」→ **21 分鐘、22,276 個 reasoning token**，
  產出 3,223 token。關掉 reasoning：3,715 token、137 秒。
- 「draw an svg of a circle」→ reasoning trace 開始討論
  「deep teal ink on warm paper 還是 Bauhaus 風的 bold vermilion」。

第一週社群最常見的抱怨不是品質而是 **verbosity**：
agent loop 裡別的模型用 1k token 的地方它用 10k。

**反面意見**（OVERBRING Labs）值得認真對待：
對 agentic coding 而言重要的不是 tok/s 而是**到達正確結果的 wall-clock time**。
他們用 `xhigh` 跑一個真實的跨三 repo 除錯任務，10 分鐘內找到 root cause 並修好，
沒有出現 doom loop，結論是它「不是在過度思考，是在思考任務與子任務」。

兩邊都對，因為在講不同的工作。互動式用 `low`，一般 coding 用 `medium`，
無人值守的長 horizon 任務 `xhigh` 可能真的划算。

### 4.2 262K context 是能力不是預設值

KV cache 換算（64 KB/token, f16）：

| Context | f16 | q8_0 | q4_0 |
|---|---|---|---|
| 8K | 0.5 GB | 0.25 GB | 0.13 GB |
| 32K | 2 GB | 1 GB | 0.5 GB |
| 128K | 8 GB | 4 GB | 2 GB |
| 262K | **16 GB** | 8 GB | 4 GB |

262K 光 KV cache 就吃掉一張 16 GB 卡。24 GB 卡的公開測試中，
最高穩定 context 是 **64K**。本機（13.5 GiB 可用）是 **32K**。

另外，1M 的 YaRN context 在開源權重上實質是 server 功能，
而且 static YaRN 會傷害短 prompt 品質。

### 4.3 chat template bug

社群在 2026-08 中回報：傳 `enable_thinking=false` 會觸發 fatal exception，
建議拿社群修好的 template。

**本機實測（unsloth UD-Q3_K_XL + llama.cpp build 10481）沒有重現。**
但換 GGUF publisher 或降版 llama.cpp 時要重新確認。

---

## 5. 結論

### 對這台機器

見 [04-benchmarks.md](04-benchmarks.md) 與 [02-operations.md](02-operations.md)。
一句話：**UD-Q3_K_XL 全常駐 + MTP，113 t/s。**

### 對一般選型

| 可用 VRAM | 選擇 |
|---|---|
| 12 GB | UD-IQ3_XXS / UD-Q2_K_XL（品質妥協明顯） |
| **13.5 GiB（本機）** | **UD-Q3_K_XL + 32K q8_0 KV + MTP n4** |
| 20 GB | IQ4_XS / Q4_K_M |
| 24 GB | **UD-Q4_K_XL**（最佳預設） |
| 32 GB (5090) | Q6_K，或 NVFP4 走 vLLM/SGLang（200+ t/s） |
| 48 GB+ | Q8_0 / BF16 |

### 對使用模式

多位獨立評測者收斂到同一個模式：

> **API 處理最難的 5%，本地模型處理量與任何不能離開這台機器的東西。**

理由：本地跑得動 ≠ 跑得夠快，長 agent loop 在消費硬體上仍然痛苦；
最難的 5% 正是前沿模型還在賺訂閱費的地方。
但**隱私是壓倒性的論證** —— Apache 2.0 權重完全離線運作，
跟法遵部門的對話跟「託管 API 的服務條款」是完全不同的性質。

---

## 資料來源與證據等級

| 來源 | 類型 | 用途 |
|---|---|---|
| [Qwen 官方 model card](https://huggingface.co/Qwen/Qwen3.8-27B) | 官方文件 / vendor benchmark | 架構規格、sampling 建議、benchmark |
| [unsloth/Qwen3.8-27B-GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) | 官方 repo（HF API 實抓） | 量化階梯與檔案大小 |
| [Quesma 量化受控研究](https://quesma.com/blog/qwen-quantization-quality/) | **獨立受控實驗** | 量化品質的核心證據 |
| [Simon Willison](https://simonwillison.net/2026/Aug/16/qwen-38-27b/) | 獨立第一手實測 | xhigh 過度思考、vision、agent loop |
| [Thomas Wiegold](https://thomas-wiegold.com/blog/qwen-3-8-27b-best-local-llm/) | 獨立分析 | KV cache 數學、硬體門檻 |
| [kingy.ai 檔案選擇指南](https://kingy.ai/blog/qwen3-8-27b-best-quantization-gguf/) | source-audited 彙整 | 跨 publisher 檔案差異 |
| [kingy.ai 24GB 三方對比](https://kingy.ai/blog/qwen3-8-27b-vs-qwen3-6-27b-vs-gemma-4-31b/) | 第三方受控測試 | vs Qwen3.6 / Gemma 4 |
| [NxCode](https://www.nxcode.io/resources/news/qwen3-8-27b-local-agent-model-2026) | 分析報導 | 架構未變的佐證 |
| [VentureBeat](https://venturebeat.com/technology/qwen3-8-27b-runs-frontier-class-coding-agents-and-reasoning-locally-no-cloud-api-required) | 新聞 | 社群反應彙整 |
| [OVERBRING Labs](https://overbring.com/blog/2026-08-17-qwen3-8-27b-wall-clock/) | 獨立實測 | wall-clock 論點、KV q4 反例 |
| [kelcode.co.uk](https://kelcode.co.uk/qwen3-8-27b-is-qwens-new-27b-model-actually-better/) | 獨立實測 | tool-eval-bench 3.6 vs 3.8 |
| [vellum Open LLM Leaderboard](https://www.vellum.ai/open-llm-leaderboard) | 第三方榜 | 開源前沿模型對比 |
| [sudoingX/qwen38-mtp](https://github.com/sudoingX/qwen38-mtp) | 社群 benchmark 集（53 組設定 / 40 貢獻者） | MTP 調校規則 |
| [dev.to：587 則 HN 留言彙整](https://dev.to/_1a008d053e73e4a54d13a/qwen-38-27b-one-week-in-what-587-hn-comments-actually-say-about-running-it-1ejn) | 社群意見彙整 | KLD vs benchmark 之爭 |

**未能取得**：使用者提供的兩個 reddit.com/r/LocalLLaMA 連結（403）、
freedidi.com（CAPTCHA）、zhihu 專欄（403）。已用上表的等價來源補齊。
