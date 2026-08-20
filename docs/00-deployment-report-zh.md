# Qwen3.8-27B 本機部署報告

> 對象機器：RTX 5070 Ti 16GB / Intel Ultra 7 265K / 88 GB RAM / WSL2 Ubuntu 24.04
> 完成日期：2026-08-19
> 狀態：**已部署並驗證運行中**

一份研究 + 實測 + 部署的完整紀錄。回答三個問題：
Qwen3.8-27B 值不值得跑、這台機器該跑哪個量化版本、以及之後怎麼開怎麼改。

---

## TL;DR

| | |
|---|---|
| **模型檔** | `unsloth/Qwen3.8-27B-GGUF` → **`Qwen3.8-27B-UD-Q3_K_XL.gguf`**（13.44 GB） |
| **Runtime** | `ghcr.io/ggml-org/llama.cpp:full-cuda`（build 10481），docker |
| **實測速度** | **113.3 tok/s**（32K context，開 MTP speculative decoding） |
| **Endpoint** | `http://127.0.0.1:8088/v1`（OpenAI 相容） |
| **啟動** | `qwen38 agent` |
| **設定檔** | `~/.config/qwen38.env` |

**最反直覺的結論**：這台機器要選 **3-bit** 而不是所有指南都推薦的 4-bit。
不是因為 3-bit 比較好，而是 4-bit 塞不進 VRAM，
而這個模型架構的 CPU offload 懲罰是 **1 層 = −60% 速度**。
19 倍速度差，換受控測試量到的 0–5% 品質差。

---

## 立刻開始

```bash
qwen38 agent                 # 啟動（預設 profile）
qwen38 status                # 看狀態 / VRAM / endpoint
qwen38 stop                  # 停止

curl http://127.0.0.1:8088/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-27b","reasoning_effort":"low",
       "messages":[{"role":"user","content":"你好"}],
       "max_tokens":1200}'
```

⚠️ **兩個一定要記的事**（不記會以為模型壞了）：
1. `reasoning_effort` 預設是 `xhigh`，會為了「畫一個圓」討論配色好幾分鐘。**先設 `low`**。
2. **`max_tokens` 給 ≥1200**。thinking token 也算進去，給 400 會讓 `content` 回傳空字串。

---

## 文件

| 文件 | 內容 |
|---|---|
| [docs/01-what-was-done.md](docs/01-what-was-done.md) | **我做了什麼** — 完整變更清單、新增/修改的檔案、被停掉的服務、磁碟用量 |
| [docs/02-operations.md](docs/02-operations.md) | **怎麼開、怎麼改 endpoint** — profile 說明、設定檔、port/bind/API key、疑難排解 |
| [docs/03-research-report.md](docs/03-research-report.md) | **研究報告** — Qwen3.8-27B 是什麼、對比前沿模型、量化品質證據、資料來源與可信度 |
| [docs/04-benchmarks.md](docs/04-benchmarks.md) | **實測數據** — 18 組設定的完整 benchmark 與三個非顯而易見的發現 |

延伸知識庫（依 hermes `llm-wiki` skill 建立，22 頁）：`/home/kino/llm-wiki/`

---

## 檔案位置速查

```
/home/kino/git/qwen3.8test/     ← 本報告
/home/kino/models/qwen3.8-27b/  ← 模型檔 + 維運腳本（50 GB）
  └── _ops/qwen38.sh            ← 啟動器（symlink: ~/.local/bin/qwen38）
/home/kino/.config/qwen38.env   ← 設定檔（port / bind / API key）
/home/kino/llm-wiki/            ← 知識庫（22 頁 + 6 份 raw sources）
```
