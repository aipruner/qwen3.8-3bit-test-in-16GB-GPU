# 01 — 我做了什麼

2026-08-19 這個 session 對這台機器做的所有變更，依「新增 / 修改 / 停止 / 未動」分類。

---

## ✅ 新增的東西

### 1. 模型檔（`/home/kino/models/qwen3.8-27b/`，共 50 GB）

| 檔案 | 大小 | 用途 |
|---|---|---|
| `Qwen3.8-27B-UD-Q3_K_XL.gguf` | 13.4 GB | **實際使用** |
| `Qwen3.8-27B-IQ4_XS.gguf` | 15.7 GB | 對照組（升級 24GB 卡才用得上） |
| `Qwen3.8-27B-UD-Q4_K_XL.gguf` | 17.9 GB | 對照組（同上） |
| `mmproj-F16.gguf` | 0.93 GB | vision profile 用 |
| `mtp-Qwen3.8-27B-Q4_0.gguf` | 1.68 GB | **未使用**（MTP head 已內嵌在主檔） |
| `mtp-Qwen3.8-27B-Q8_0.gguf` | 3.16 GB | **未使用**（同上） |

> 想回收空間：`rm /home/kino/models/qwen3.8-27b/{Qwen3.8-27B-IQ4_XS.gguf,Qwen3.8-27B-UD-Q4_K_XL.gguf,mtp-*.gguf}` → 釋出 38 GB。
> 磁碟目前 `/` 剩 573 GB，不急。

### 2. 維運腳本（`/home/kino/models/qwen3.8-27b/_ops/`）

| 檔案 | 用途 |
|---|---|
| `qwen38.sh` | 啟動器。4 個 profile + status/logs/stop/url，內建 VRAM 預檢 |
| `bench-server.sh` | A/B benchmark harness。啟 server → 送固定 prompt → 記錄 timings → 關閉 |
| `restart-voxscene.sh` | 還原被停掉的 `voxscene serve`（見下方「已停止」） |

### 3. 設定檔

- `/home/kino/.config/qwen38.env` — port / bind / API key / 模型檔，改完直接生效
- `/home/kino/.local/bin/qwen38` — symlink 指向 `_ops/qwen38.sh`，讓你直接打 `qwen38`

### 4. Docker image

- 拉了 `ghcr.io/ggml-org/llama.cpp:full-cuda`（10.3 GB，磁碟上 3.57 GB）
- 建立常駐 container `qwen38`（`--restart unless-stopped`，開機後 docker 起來會自動接續）

> Linux 版 llama.cpp **沒有官方 CUDA 預編譯 binary**（只有 Windows 有），
> 用 docker image 省掉裝 CUDA toolkit + 編譯。實測在 WSL2 直接認得 sm_120 Blackwell。

### 5. 知識庫 `/home/kino/llm-wiki/`

依 hermes 的 `llm-wiki` skill 建立，與 `~/wiki`（SDD 領域）分開。
**22 頁 + 6 份 raw sources**，繁中為主、專有名詞保留英文。Lint 全綠。

- `entities/` 5 頁：qwen3.8-27b · llama-cpp · ollama · unsloth · rtx-5070ti-16gb
- `concepts/` 13 頁：quantization · gguf · gguf-quant-types · unsloth-dynamic-quant · kv-cache ·
  gated-deltanet-hybrid-attention · cpu-offload · mtp-speculative-decoding · vram-budget ·
  reasoning-effort-and-overthinking · agentic-reliability-compounding · context-length-and-yarn · vision-mmproj
- `comparisons/` 3 頁：qwen3.8-27b-quant-ladder · qwen3.8-27b-vs-frontier-2026-08 · inference-engine-comparison
- `queries/` 1 頁：kino-rtx5070ti-deployment
- `raw/` 6 份：官方 model card · Unsloth 階梯 · Quesma 量化研究 · Simon Willison · Thomas Wiegold · **本機實測數據**

### 6. 記憶檔（`~/.claude/projects/-home-kino-git-qwen3-8test/memory/`）

- `rtx5070ti-usable-vram.md` — 顯示器佔 2.4 GB，VRAM 預算只能算 13.5 GiB
- `qwen38-local-deployment.md` — 部署位置、啟動指令、wiki 位置

---

## ⏸️ 已停止（需要你決定要不要還原）

**`voxscene serve` 的 3 個 instance 目前是停止狀態。**

它們是 2026-08-16 由前一個 Claude session 啟動的，data-root 在 scratchpad：

| Port | data-root |
|---|---|
| 26605 | `.../real/journeydata2` |
| 26606 | `.../real/redubjourney` |
| 26607 | `.../real/redubjourney2` |

還原：

```bash
bash /home/kino/models/qwen3.8-27b/_ops/restart-voxscene.sh
```

⚠️ 但它跟 LLM 會搶 VRAM（目前只剩 454 MiB），建議二選一。

> **實測補充**：原本以為 voxscene 佔 3 GB，實際只佔 **690 MiB**。
> 剩下的 2.4 GB 是 **Windows 桌面本身**（顯示器接在這張卡上），那個拿不回來。
> 這是整件事最重要的硬體發現 —— 詳見 [04-benchmarks.md](04-benchmarks.md)。

---

## 🚫 沒有動的東西

- **Ollama**（v0.15.6）與它的兩個 embedding 模型完全沒動
- 其他 docker container（`bgutil-provider`、`speaches`、`postgres` ×2、`telegram-bot-api`）沒動
- `~/wiki`（SDD 領域知識庫）沒動 —— 新的 LLM 知識放在獨立的 `~/llm-wiki`
- 沒有安裝 CUDA toolkit、沒有編譯任何東西、沒有改系統設定

---

## 📋 驗證結果

| 項目 | 結果 |
|---|---|
| 繁體中文輸出 | ✅ 專有名詞正確保留英文 |
| `reasoning_effort: low` | ✅ reasoning trace 縮到 257 字元，81 t/s |
| Tool calling（OpenAI function 格式） | ✅ `finish_reason=tool_calls`，參數正確 |
| `enable_thinking: false` | ✅ **未重現**社群回報的 fatal exception |
| Vision（bbox_2d） | ✅ 實際 `[300,250,700,750]` → 模型 `[350,250,650,750]` |
| 端到端中文技術問答 | ✅ 85.4 t/s |
| Endpoint bind 設定 | ✅ 只綁 loopback，從 WSL IP 連不到（符合預期） |

---

## ⚠️ 一個研究上的限制要說清楚

**你給的 6 個連結有 4 個抓不到**：

| 連結 | 結果 |
|---|---|
| `huggingface.co/Qwen/Qwen3.8-27B` | ✅ 成功 |
| `huggingface.co/unsloth/Qwen3.8-27B-GGUF` | ✅ 成功（另用 HF API 抓完整檔案清單） |
| 兩個 `reddit.com/r/LocalLLaMA` 連結 | ❌ 403（WebFetch / exa / curl / jina reader 全被擋） |
| `freedidi.com/25144.html` | ❌ CAPTCHA 牆 |
| `zhuanlan.zhihu.com/p/2071984701632419778` | ❌ 403 |

改用等價來源補齊：Simon Willison、Thomas Wiegold、**Quesma 量化受控研究**、
kingy.ai、VentureBeat、OVERBRING Labs、kelcode.co.uk、vellum.ai、
augmentedmind.substack、以及一篇彙整 587 則 HN 留言的 dev.to 文章。
完整清單記在 `/home/kino/llm-wiki/log.md`。
