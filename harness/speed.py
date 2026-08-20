import os, requests, time, sys
BASE=os.environ.get("QWEN_URL", "http://127.0.0.1:18038/v1").rstrip("/")
PROMPTS=[("code","Write a Python class implementing an LRU cache with get/put in O(1). Code only, no explanation."),
         ("prose","Explain in flowing English prose, with no lists and no code, why memory bandwidth limits dense transformer inference."),
         ("code2","Write a single-file HTML page with a canvas that draws an animated bouncing ball. Code only.")]
tot=[]
for tag,p in PROMPTS:
    t0=time.time()
    r=requests.post(BASE+"/chat/completions",json={"model":"qwen3.8-27b","messages":[{"role":"user","content":p}],
        "temperature":0.7,"top_p":0.8,"max_tokens":600,"reasoning_effort":"low"},timeout=1200).json()
    tm=r.get("timings",{}) or {}
    print("%-6s wall=%5.1fs  gen=%6.1f tok/s  read=%6.0f tok/s  out=%d" % (
        tag, time.time()-t0, tm.get("predicted_per_second",0), tm.get("prompt_per_second",0),
        r["usage"]["completion_tokens"]), flush=True)
    tot.append(tm.get("predicted_per_second",0))
print("mean gen = %.1f tok/s" % (sum(tot)/len(tot)))
