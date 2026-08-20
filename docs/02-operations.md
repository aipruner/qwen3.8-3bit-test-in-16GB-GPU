# 02 — 怎麼啟動、怎麼改 Endpoint

---

## 1. 啟動與停止

```bash
qwen38 agent      # 預設 profile，啟動
qwen38 status     # 容器狀態 + VRAM + endpoint + health
qwen38 logs       # tail -f 容器 log
qwen38 stop       # 停止
qwen38 url        # 只印出 endpoint URL（給腳本用）
```

`qwen38` 是 `~/.local/bin/qwen38` 的 symlink，指向
`/home/kino/models/qwen3.8-27b/_ops/qwen38.sh`。
若打 `qwen38` 找不到指令，`~/.local/bin` 不在 PATH：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

### 開機自動啟動

container 是用 `--restart unless-stopped` 建的，
**docker daemon 起來就會自動接續**，除非你手動 `qwen38 stop` 過。

如果你 `qwen38 stop` 過想恢復自動啟動，再跑一次 `qwen38 agent` 即可。

---

## 2. Profile

**Source of truth is `ops/qwen38.sh` in this repo, not this table.**
The 2026-08-19 numbers below are historical. `agent` at 32K spills on this
card; the published MTP config is `safe` (24K). DFlash 2 is `dflash` (8K)
and needs `local/llama.cpp:dflash2-cuda` — see `docs/05-dflash2.md`.

| Profile | context | KV cache | spec | 適用 |
|---|---|---|---|---|
| `safe` | 24K | `q8_0` | native MTP n-max 4 | **日常**：第一篇文章的設定 |
| `agent` | 32K | `q8_0` | native MTP n-max 4 | 會溢出，不要當預設 |
| `long` | 32K | `q4_0` | native MTP n-max 4 | 同樣 32K，KV 較省、精度較低 |
| `vision` | 16K | `q8_0` | 關 spec | mmproj。**與 MTP 互斥** |
| `dflash` | 8K | `q8_0` | DFlash 2 n-max 4 | 2026-08-21 對照組。多佔 ~1.1 GiB draft |
| `dflash-ngram` | 8K | `q8_0` | DFlash 2 + ngram-mod | 實驗用，品質套件沒跑過 |

切 profile 直接跑 `./ops/qwen38.sh <profile>` 即可：腳本會先停掉自己的 container 再量剩餘 VRAM。
`dflash` / `dflash-ngram` 會自動改用 `local/llama.cpp:dflash2-cuda`。

---

## 3. 改 Endpoint

所有設定集中在 **`~/.config/qwen38.env`**，改完直接生效，不用動腳本。

```bash
# ~/.config/qwen38.env
QWEN38_PORT=8088          # 對外 port
QWEN38_BIND=127.0.0.1     # 綁定介面
# QWEN38_API_KEY=         # 設了就要求 Authorization: Bearer <key>
# QWEN38_MODEL=Qwen3.8-27B-UD-Q3_K_XL.gguf
# QWEN38_NAME=qwen38      # docker container 名稱
# QWEN38_MODELS=/home/kino/models/qwen3.8-27b
```

改完 **要重啟才生效**：`qwen38 stop && qwen38 agent`

### 常見情境

#### 換 port（8088 被佔用了）

```bash
sed -i 's/^QWEN38_PORT=.*/QWEN38_PORT=9000/' ~/.config/qwen38.env
qwen38 stop && qwen38 agent
# → http://127.0.0.1:9000/v1
```

或臨時用環境變數覆寫（不改檔案）：

```bash
QWEN38_PORT=9000 qwen38 agent
```

> ⚠️ 環境變數的優先序**高於**設定檔。用環境變數啟動後，
> 之後 `qwen38 status` / `qwen38 stop` 也要帶同樣的變數，否則它會去看設定檔的 port。

#### 讓區網其他機器連得到

預設只綁 `127.0.0.1`（loopback），只有這台機器連得到。
從 Windows 端連 `localhost:8088` 仍然可以（WSL2 有 localhost forwarding）。

要開放給區網：

```bash
sed -i 's/^QWEN38_BIND=.*/QWEN38_BIND=0.0.0.0/' ~/.config/qwen38.env
# 開放到區網時強烈建議同時設 API key
echo 'QWEN38_API_KEY=請換成你自己的隨機字串' >> ~/.config/qwen38.env
qwen38 stop && qwen38 agent
```

WSL2 的額外一步：WSL2 有自己的 NAT 網段（本機是 `172.17.146.211`），
區網其他機器要連到，還需要在 **Windows 端**做 port proxy（PowerShell 以系統管理員身分）：

```powershell
netsh interface portproxy add v4tov4 `
  listenport=8088 listenaddress=0.0.0.0 `
  connectport=8088 connectaddress=$(wsl hostname -I).Trim()
New-NetFirewallRule -DisplayName "qwen38" -Direction Inbound -LocalPort 8088 -Protocol TCP -Action Allow
```

> ⚠️ WSL2 的 IP 每次重開機會變，portproxy 要重設。

#### 同時跑兩個實例

```bash
QWEN38_NAME=qwen38b QWEN38_PORT=8089 QWEN38_MODEL=Qwen3.8-27B-IQ4_XS.gguf qwen38 safe
```

⚠️ 這台的 VRAM 塞不下兩個 27B。實務上只有在跑不同大小的模型時才有意義。

---

## 4. 呼叫方式

### curl

```bash
curl http://127.0.0.1:8088/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.8-27b",
    "reasoning_effort": "low",
    "messages": [{"role":"user","content":"用繁體中文解釋什麼是 KV cache"}],
    "max_tokens": 1200,
    "temperature": 1.0, "top_p": 0.95, "top_k": 20
  }'
```

### OpenAI SDK（Python）

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8088/v1", api_key="dummy")

r = client.chat.completions.create(
    model="qwen3.8-27b",
    messages=[{"role": "user", "content": "..."}],
    max_tokens=1200,
    extra_body={"reasoning_effort": "low"},
)
print(r.choices[0].message.content)
```

### 接進 agent harness（Claude Code / Pi / Aider / Continue 等）

大部分工具吃 OpenAI 相容設定：

```
base_url : http://127.0.0.1:8088/v1
api_key  : dummy   （除非你設了 QWEN38_API_KEY）
model    : qwen3.8-27b
```

Web UI 直接開瀏覽器到 `http://127.0.0.1:8088` 就有。

---

## 5. 必須知道的 Runtime 參數

### `reasoning_effort` —— 一定要降

| 值 | 用途 |
|---|---|
| `xhigh`（**模型預設**） | 無人值守的長 horizon 除錯 / 多步驟規劃 |
| `medium` | 一般 coding、寫測試、重構 |
| `low` | 互動式聊天、翻譯、簡單問答 ← **平常用這個** |

完全關掉 thinking：

```json
{"chat_template_kwargs": {"enable_thinking": false}}
```

> 為什麼重要：Simon Willison 用預設 `xhigh` 畫一隻 pelican，
> 花了 **21 分鐘、22,276 個 reasoning token**。叫它「畫一個圓」，
> 它會開始討論 Bauhaus 配色。

### `max_tokens` —— 給足，至少 1200

**thinking token 也算在 `max_tokens` 裡。**
本機實測：一個三句話的中文問答在 `reasoning_effort: low` 之下
仍用掉 766 字元的 reasoning。`max_tokens: 400` 會讓 `content` 回傳**空字串**
（預算全被 reasoning 吃光）。這是最容易誤判成「模型壞了」的症狀。

### 官方建議的 sampling 參數

```
thinking mode : temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0
instruct mode : temperature=0.7, top_p=0.80, top_k=20, min_p=0.0, presence_penalty=1.5
```

---

## 6. 疑難排解

### 「啟動了但超級慢」（個位數 tok/s）

**這是最常見也最隱蔽的問題。** WSL2 超過 VRAM **不會回報 OOM**，
它會把權重溢出到 shared system memory，服務照樣啟動、health 照樣 `ok`，
只是 tg 從 113 t/s 掉到個位數。

```bash
nvidia-smi --query-gpu=memory.used,memory.free --format=csv
```

`memory.free` 低於 ~300 MiB 就是這個問題。解法：

1. 關掉吃 VRAM 的東西（瀏覽器硬體加速、遊戲、其他推論服務、voxscene）
2. `qwen38 stop && qwen38 safe`（24K context，省 VRAM）

啟動器已內建預檢：free < 13,300 MiB 會警告並列出佔用者。

### 「`qwen38 agent` 被預檢擋下來」

舊的 container 還在跑。先 `qwen38 stop`。

### 「回應是空的 / `content` 是空字串」

`max_tokens` 太小，被 reasoning 吃光。給到 1200 以上。

### 「tool call 參數亂掉 / 長 context 後突然變笨 / 陷入修正迴圈」

**第一個要排除的是 KV cache 量化**，不是 prompt 也不是模型檔。
如果你在用 `long` profile（`q4_0` KV），切回 `agent`（`q8_0` KV）。

### 「想確認 MTP 真的有開」

```bash
qwen38 logs | grep -i "draft acceptance"
# → draft acceptance = 0.837 (538 accepted / 643 generated), mean len = 4.34
```

沒有這行就是沒開。acceptance 掉到 0.6 以下的話值得重掃 `--spec-draft-n-max`。

### 重新調校（llama.cpp 更新後）

llama.cpp upstream 每週的 kernel 優化會讓 baseline 移動 10–15%，
`n-max 4` 這個最佳值**會過期**。重掃：

```bash
cd /home/kino/models/qwen3.8-27b/_ops
docker pull ghcr.io/ggml-org/llama.cpp:full-cuda
qwen38 stop
for n in 2 3 4 5; do
  ./bench-server.sh "n-max $n" -c 32768 -ctk q8_0 -ctv q8_0 \
    --spec-type draft-mtp --spec-draft-n-max $n --parallel 1
done
```

⚠️ 測之前確認系統沒有其他負載 —— 第一輪 benchmark 在模型下載中跑，
量到的數字只有真實值的 45%。

---

## 7. 完整參數對照（`agent` profile 實際跑的指令）

```bash
docker run -d --restart unless-stopped --name qwen38 --gpus all \
  -p 127.0.0.1:8088:8080 \
  -v /home/kino/models/qwen3.8-27b:/models \
  --entrypoint /app/llama-server \
  ghcr.io/ggml-org/llama.cpp:full-cuda \
    -m /models/Qwen3.8-27B-UD-Q3_K_XL.gguf \
    --host 0.0.0.0 --port 8080 \
    -ngl 99 \                          # 全部 64 層上 GPU（1 層落 CPU = −60%）
    -fa 1 \                            # flash attention
    --jinja \                          # 用 GGUF 內嵌 chat template（tool calling 必要）
    --parallel 1 \                     # MTP 只在單一 request 下有效益
    -t 20 \                            # CPU threads
    --alias qwen3.8-27b \
    -c 32768 \                         # context
    -ctk q8_0 -ctv q8_0 \              # KV cache 量化（必須對稱！）
    --spec-type draft-mtp \            # MTP speculative decoding
    --spec-draft-n-max 4
```

每個參數為什麼是這個值 → [04-benchmarks.md](04-benchmarks.md)
