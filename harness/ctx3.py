import os, requests, random, string
BASE=os.environ.get("QWEN_URL", "http://127.0.0.1:18038/v1").rstrip("/")
ROOT=BASE.removesuffix("/v1")
P=("The runtime appends key and value projections to a preallocated buffer instead of "
   "recomputing them for every step, trading memory for compute. Profiling shows the "
   "bottleneck shifting from arithmetic throughput toward memory bandwidth as batch size falls. ")
def ntok(t):
    return len(requests.post(ROOT+"/tokenize",json={"content":t},timeout=120).json()["tokens"])
per=ntok(P)
print("tokens per paragraph:",per)
print(f"{'ctx_tok':>8} {'pp t/s':>9} {'tg t/s':>8} {'ttft_s':>7}")
for target in [1000, 8000, 16000, 24000, 30000]:
    salt="".join(random.choice(string.ascii_letters) for _ in range(24))   # cache-bust
    doc=(salt+" ")+P*max(1,round(target/per))
    body={"model":"qwen3.8-27b","messages":[{"role":"user","content":doc+
        "\n\nWrite exactly three sentences explaining what a KV cache is."}],
        "max_tokens":300,"temperature":0.7,"reasoning_effort":"low"}
    r=requests.post(BASE+"/chat/completions",json=body,timeout=900).json()
    if "timings" not in r: print(target,"ERR",str(r)[:140]); continue
    t=r["timings"]
    print(f"{t['prompt_n']:>8} {t['prompt_per_second']:>9.1f} {t['predicted_per_second']:>8.2f} {t['prompt_ms']/1000:>7.2f}")
