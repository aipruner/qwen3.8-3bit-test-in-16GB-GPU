# 04 — 實測數據

*2026-08-19 · RTX 5070 Ti 16GB / Intel Ultra 7 265K / WSL2 · llama.cpp build 10481 (`25ae3a9b3`)*

---

## 測試環境

| | |
|---|---|
| GPU | NVIDIA GeForce RTX 5070 Ti，16,303 MiB，compute capability **12.0 (sm_120, Blackwell)** |
| 記憶體頻寬 | GDDR7 256-bit ≈ **896 GB/s** |
| **顯示器** | **接在這張卡上**（`nvidia-smi` `Disp.A = On`） |
| CPU | Intel Core Ultra 7 265K，20 cores（無 HT），L3 30 MiB |
| RAM | 88 GiB 配給 WSL2 |
| Driver / CUDA | 591.86 / CUDA 13.1 |
| Runtime | `ghcr.io/ggml-org/llama.cpp:full-cuda`，build 10481 |
| Model repo | `unsloth/Qwen3.8-27B-GGUF` |

---

## 🔑 發現 0：可用 VRAM 是 13.5 GiB，不是 16 GB

**這個數字決定了後面所有的選擇。**

| 狀態 | GPU used | free |
|---|---|---|
| 一切照常（含 voxscene） | 3,090 MiB | 13,213 MiB |
| 停掉 voxscene 後 | **2,404 MiB** | **13,592 MiB** |

停掉推論服務只換回 **690 MiB**。剩下的 **2,400 MiB 是 Windows 桌面本身**，
拿不回來（`nvidia-smi` 顯示 `No running processes found`，
20% GPU util 來自桌面合成）。

> **做 VRAM 預算時 16 GB 顯卡只能當 13.5 GiB 算。**
> 這 2.4 GB 的差距，直接讓「該用 4-bit 還是 3-bit」得到相反的答案。

---

## A. llama-bench：量化 × offload

`-fa 1`，`-p 512 -n 128`，`-r 3`，**GPU 完全閒置**。

| 檔案 | 大小 | `-ngl` | CPU 上的層數 | pp512 (t/s) | tg128 (t/s) | 相對 |
|---|---|---|---|---|---|---|
| **UD-Q3_K_XL** | 12.51 GiB | 99 | **0** | 1929.97 ± 80.21 | **54.40 ± 0.40** | **100%** |
| IQ4_XS | 14.62 GiB | 63 | 1 | 1525.38 ± 150.05 | 21.75 ± 1.78 | 40% |
| IQ4_XS | 14.62 GiB | 60 | 4 | 1274.67 ± 55.67 | 13.97 ± 2.54 | 26% |
| UD-Q4_K_XL | 16.68 GiB | 50 | 14 | 654.33 ± 21.49 | 6.05 ± 0.37 | 11% |

### 🔑 發現 1：1 層落在 CPU = −60% 速度

一般 dense transformer 的 offload 代價大致按比例
（CPU 上的權重量 ÷ 記憶體頻寬）。**這個架構不是。**

原因是 [Gated DeltaNet 的 hybrid 布局](03-research-report.md)：
48 個 linear attention 層帶著 **recurrent state，每個 token 都要跨裝置同步**。
這個成本與 CPU 上的權重量無關，所以「只 offload 一點點」不會只慢一點點。

### `-ot` 只把 FFN 丟 CPU 也救不了

```
-ot "blk\.(5[2-9]|6[0-3])\.ffn_(up|down|gate)\.weight=CPU"   # 12 層的 FFN
→ pp 1138.69 / tg 8.94 t/s
```

與整層 offload 同級。這條路走不通。

### ⚠️ 方法論警告

第一輪 benchmark 是在**模型還在下載時**跑的（IO + CPU 被吃滿），
UD-Q3_K_XL 全常駐量到 **tg = 24.25**；GPU/IO 閒置後重測是 **54.40**。
**差了 2.2 倍。** 任何 offload 比較都必須確認系統無其他負載。

---

## B. llama-server：context × KV cache × MTP

UD-Q3_K_XL，`-ngl 99 -fa 1`，單一 request，700 output tokens。

| # | context | KV cache | MTP | pp (t/s) | tg (t/s) | draft acceptance | GPU used |
|---|---|---|---|---|---|---|---|
| A | 32K | f16 | off | 187.2 | 49.50 | — | 15,679 MiB |
| B | 32K | q8_0 / q8_0 | off | 206.1 | 49.00 | — | 14,904 MiB |
| C | 32K | q8_0 / q8_0 | n-max 2 | 176.1 | 88.85 | 0.892 (len 2.78) | 15,307 MiB |
| D | 32K | q8_0 / q8_0 | n-max 3 | 174.1 | 100.25 | 0.846 (len 3.53) | 15,435 MiB |
| **E** ⭐ | **32K** | **q8_0 / q8_0** | **n-max 4** | **191.0** | **113.27** | **0.837 (len 4.34)** | **15,588 MiB** |
| I | 32K | q4_0 / q4_0 | n-max 4 | 151.7 | 112.69 | 0.793 | 14,856 MiB |
| J | 24K | q8_0 / q8_0 | n-max 4 | 219.1 | 116.89 | 0.794 | 15,024 MiB |
| K | 32K | q8_0 / **q4_0** | n-max 4 | 155.7 | **62.79** | 0.788 | 15,000 MiB |
| L | 40K | q8_0 / **q4_0** | n-max 4 | 144.9 | **69.23** | 0.789 | 15,255 MiB |
| — | 48K | q8_0 / q8_0 | n-max 4 | ❌ 失敗 | | | 16,200+ MiB |
| — | 64K | q8_0 / q8_0 | n-max 3 | ❌ 失敗 | | | 15,922 MiB |
| — | 64K | q4_0 / q4_0 | n-max 4 | ❌ 失敗 | | | — |

⭐ = 採用的設定（`agent` profile）

### 🔑 發現 2：MTP 是最大的單一加速來源（+131%）

49.0 → 113.3 t/s，而且**不需要額外的 draft model** ——
nextn head 已內嵌在 GGUF 裡。驗證方式：

```bash
docker run --rm -v /home/kino/models/qwen3.8-27b:/models \
  --entrypoint python3 ghcr.io/ggml-org/llama.cpp:full-cuda -c "
import sys; sys.path.insert(0,'/app/gguf-py')
from gguf import GGUFReader
r = GGUFReader('/models/Qwen3.8-27B-UD-Q3_K_XL.gguf')
print([t.name for t in r.tensors if 'nextn' in t.name])"
# → ['blk.64.nextn.eh_proj.weight', 'blk.64.nextn.enorm.weight',
#    'blk.64.nextn.hnorm.weight', 'blk.64.nextn.shared_head_norm.weight']
```

注意 n-max 從 2 到 4，acceptance rate 從 0.892 降到 0.837，
但**平均 draft 長度**從 2.78 升到 4.34 —— 淨效益仍是正的。

> 最佳 n-max 隨顯卡而異（社群數據：RTX 3090/4090 常在 2，5090 / RX 7900 XTX 在 3–4）。
> **必須自己掃過一次**，而且 llama.cpp 每週的優化會讓它過期。

### 🔑 發現 3：KV cache 不要用混合精度

`-ctk q8_0 -ctv q4_0`（K 高精度、V 低精度）在理論上很合理 ——
K 對量化比 V 敏感。**實測只有對稱 q8_0 的 55% 速度**（62.79 vs 113.27）。

原因：K/V 型別不同時，fused attention kernel 走 fallback path，
代價遠大於省下的記憶體。**對稱就對了。**

### 🔑 發現 4：WSL2 超過 VRAM 不會 OOM，只會無聲變慢

48K / 64K 的失敗方式不是報錯，而是：

- 模型正常載入
- `/health` 回 `{"status":"ok"}`
- 請求正常被接受
- `memory.free` 掉到 **74–100 MiB**
- **單一請求跑超過 10 分鐘沒完成**

WDDM 把權重溢出到 shared system memory，沒有任何錯誤訊息。

> **判斷設定可行與否要看 `nvidia-smi` 的 `memory.free`，不是看服務有沒有起來。**
> 啟動器因此內建 VRAM 預檢（free < 13,300 MiB 就警告）。

### 發現 5：q4_0 KV 買的是 context 長度，不是速度

q8_0 → q4_0 的 tg 幾乎沒變（113.27 → 112.69），
省下的是 730 MiB VRAM。所以只有需要更長 context 時才降到 q4_0。

---

## C. 功能驗證

`agent` profile，`reasoning_effort: low`：

| 項目 | 結果 |
|---|---|
| 繁體中文輸出 | ✅ 專有名詞正確保留英文 |
| `reasoning_effort: low` | ✅ reasoning trace 縮到 257 字元，81.0 t/s |
| Tool calling（OpenAI function + `--jinja`） | ✅ `finish_reason=tool_calls`，`{"city":"台北","unit":"celsius"}` |
| `chat_template_kwargs.enable_thinking=false` | ✅ **未重現**社群回報的 fatal exception |
| Vision（`vision` profile + mmproj-F16） | ✅ 實際 bbox `[300,250,700,750]` → 模型 `[350,250,650,750]`（y 完全正確）<br>pp 197.2 / **tg 52.6 t/s** |
| 端到端中文技術問答 | ✅ 85.4 t/s |
| Endpoint bind = 127.0.0.1 | ✅ 從 WSL IP（172.17.146.211）連不到 |

### ⚠️ 一個容易誤判成「模型壞了」的行為

`max_tokens: 400` + `reasoning_effort: low` → **`content` 回傳空字串**。
thinking token 也算在 `max_tokens` 裡，400 全被 reasoning 吃光。
給到 1200 才拿得到答案。

---

## 最終決策

| 選項 | 品質 | 速度 | 採用 |
|---|---|---|---|
| UD-Q4_K_XL（14 層在 CPU） | 較好 | 6.05 t/s | ❌ |
| IQ4_XS（1 層在 CPU） | 較好 | 21.75 t/s | ❌ |
| **UD-Q3_K_XL（全常駐 + MTP n4）** | 受控測試量到 0–5% 差距 | **113.27 t/s** | ✅ |

**19 倍速度差，換 0–5% 品質差。**

這與所有公開指南的「不要低於 Q4」相反 ——
因為那些指南預設你有 24 GB。在 13.5 GiB 上，
「能全部放進 VRAM 的最大量化」是不可協商的約束。

---

## 重現這些數據

```bash
cd /home/kino/models/qwen3.8-27b/_ops

# llama-bench（A 組）
docker run --rm --gpus all -v /home/kino/models/qwen3.8-27b:/models \
  --entrypoint /app/llama-bench ghcr.io/ggml-org/llama.cpp:full-cuda \
  -m /models/Qwen3.8-27B-UD-Q3_K_XL.gguf -ngl 99 -fa 1 -p 512 -n 128 -r 3

# llama-server A/B（B 組）
./bench-server.sh "label" -c 32768 -ctk q8_0 -ctv q8_0 \
  --spec-type draft-mtp --spec-draft-n-max 4 --parallel 1
```

⚠️ 測之前先 `qwen38 stop`，並確認系統沒有其他 GPU/IO 負載。

原始數據也存在 `/home/kino/llm-wiki/raw/benchmarks/kino-rtx5070ti-qwen38-2026-08-19.md`。
