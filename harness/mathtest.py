import requests, json, re, subprocess, sys, os, time
BASE="http://127.0.0.1:8088/v1"
PROBS=[
 ("Q1","求最小的正整數 n，使得 n! 的十進位表示末尾恰好有 100 個 0。",405),
 ("Q2","求方程式 x^2 - 61*y^2 = 1 的最小正整數解中的 x。",1766319049),
 ("Q3","把 1 到 9 這九個數字排成一列，要求任意相鄰兩數之和都是完全平方數。這樣的排列共有幾種？",0),
 ("Q4","擲 6 顆公正的骰子，點數總和為 20 的機率化為最簡分數 a/b。求 a+b。",5653),
 ("Q5","在 1 到 200 的整數 n 中，有多少個 n 使得 n^2 + n + 41 是質數？",156),
 ("Q6","求 3^1000 的十進位表示中所有位數的數字總和。",2142),
 ("Q7","求最小的正整數 k，使得 2^k 的十進位表示以 2026 這四個數字開頭。",589),
 ("Q8","在 1 到 99999 的正整數中，有多少個 n 使得 n 和 n^2 都是回文數？",21),
]
SYS=("你是數學解題助手。請仔細推理，最後一行必須且只能是 `ANSWER: <整數>`，不要有其他文字。")
TOOLS=[{"type":"function","function":{"name":"run_python",
  "description":"Execute Python 3 code and return stdout. Use print() to output.",
  "parameters":{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]}}}]

def py(code):
    try:
        p=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True,timeout=45)
        return ((p.stdout+p.stderr)[-1500:]) or "(no output)"
    except subprocess.TimeoutExpired:
        return "TIMEOUT after 45s"

def ans_of(txt):
    m=re.findall(r"ANSWER:\s*(-?[\d,]+)", txt or "")
    if not m: return None
    try: return int(m[-1].replace(",",""))
    except: return None

def ask(prob, effort, use_tools, max_steps=8):
    msgs=[{"role":"system","content":SYS},{"role":"user","content":prob}]
    t0=time.time(); intok=outtok=0; calls=0
    for _ in range(max_steps):
        body={"model":"qwen3.8-27b","messages":msgs,"temperature":0.7,"top_p":0.8,
              "max_tokens":int(os.environ.get("MAXTOK","8000")),"reasoning_effort":effort}
        if use_tools: body["tools"]=TOOLS
        r=requests.post(BASE+"/chat/completions",json=body,timeout=3600).json()
        if "choices" not in r: return None,time.time()-t0,intok,outtok,calls
        u=r.get("usage",{}); intok+=u.get("prompt_tokens",0); outtok+=u.get("completion_tokens",0)
        m=r["choices"][0]["message"]
        msgs.append({k:v for k,v in m.items() if k in ("role","content","tool_calls")})
        tcs=m.get("tool_calls") or []
        if not tcs: return ans_of(m.get("content")), time.time()-t0, intok, outtok, calls
        for tc in tcs:
            calls+=1
            try: a=json.loads(tc["function"]["arguments"])
            except Exception: a={"code":"print('bad json')"}
            msgs.append({"role":"tool","tool_call_id":tc["id"],"content":py(a.get("code",""))[:3000]})
    return None, time.time()-t0, intok, outtok, calls

if __name__=="__main__":
    mode=sys.argv[1]          # "reason" | "tool"
    eff=sys.argv[2] if len(sys.argv)>2 else "medium"
    use=(mode=="tool")
    ok=0; W=0; I=0; O=0; C=0
    only=os.environ.get("ONLY","")
    for tag,q,truth in PROBS:
        if only and tag not in only.split(","): continue
        a,w,i,o,c=ask(q,eff,use)
        W+=w; I+=i; O+=o; C+=c
        good = (a==truth); ok+=good
        print(f"{tag} {'✓' if good else '✗'} got={a} truth={truth} {w:.0f}s out_tok={o} tool_calls={c}",flush=True)
    print(f"SUMMARY mode={mode} effort={eff} correct={ok}/8  總wall={W:.0f}s "
          f"總tok={I+O} (in {I} / out {O}) tool_calls={C}")
