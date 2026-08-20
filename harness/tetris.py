import requests, json, re, subprocess, sys, os, time, textwrap
BASE=os.environ.get("QWEN_URL", "http://127.0.0.1:18038/v1").rstrip("/")
SPEC = textwrap.dedent("""\
    做一個完整可玩的俄羅斯方塊，單一 HTML 檔，不要用任何外部函式庫或 CDN。
    只輸出一個 ```html 程式碼區塊，不要任何說明文字。

    需求：
    - canvas 繪製 10x20 的棋盤
    - 七種標準方塊 I O T S Z J L，各自顏色不同
    - 方向鍵左右移動、下加速、上旋轉，空白鍵直接落底
    - 旋轉要做撞牆回推（wall kick），不能轉出邊界或轉進已有的方塊
    - 消行、計分（一次消 1/2/3/4 行分數不同）、等級提升後下落變快
    - 顯示下一個方塊的預覽
    - 遊戲結束畫面，按 R 重新開始
    - 暫停功能（P 鍵）
    """)
CHECKS = [
 ("canvas",       r"<canvas"),
 ("ctx2d",        r"getContext\(\s*['\"]2d"),
 ("keydown",      r"addEventListener\(\s*['\"]keydown"),
 ("7pieces",      r"(?s)I.*O.*T.*S.*Z.*J.*L"),
 ("wallkick",     r"(?i)kick|offset|tryRotate|canPlace|isValid|collide"),
 ("lineclear",    r"(?i)clearLines|removeLine|lineClear|splice\("),
 ("score",        r"(?i)score"),
 ("level",        r"(?i)level"),
 ("nextpreview",  r"(?i)next"),
 ("gameover",     r"(?i)gameover|game_over|game over"),
 ("restart",      r"(?i)KeyR|['\"]r['\"]"),
 ("pause",        r"(?i)KeyP|paus"),
 ("harddrop",     r"(?i)Space|hardDrop"),
 ("loop",         r"requestAnimationFrame|setInterval"),
]
def run(i, effort="medium"):
    work=os.path.join(os.path.dirname(os.path.abspath(__file__)),"tetris_runs"); os.makedirs(work,exist_ok=True)
    t0=time.time()
    r=requests.post(BASE+"/chat/completions", json={"model":"qwen3.8-27b",
        "messages":[{"role":"user","content":SPEC}],
        "max_tokens":16000,"temperature":0.7,"top_p":0.8,"reasoning_effort":effort},
        timeout=3600).json()
    wall=time.time()-t0
    txt=r["choices"][0]["message"].get("content") or ""
    m=re.findall(r"```(?:html)?\s*\n(.*?)```", txt, re.S)
    html=m[0] if m else txt
    path=os.path.join(work,"tetris_%d.html"%i); open(path,"w").write(html)
    js="\n".join(re.findall(r"<script[^>]*>(.*?)</script>", html, re.S))
    open(os.path.join(work,"t_%d.js"%i),"w").write(js)
    p=subprocess.run(["node","--check",os.path.join(work,"t_%d.js"%i)],capture_output=True,text=True)
    syn = "OK" if p.returncode==0 else p.stderr.strip().splitlines()[-1][:70]
    feats=[n for n,pat in CHECKS if re.search(pat, html)]
    u=r.get("usage",{}); tmg=r.get("timings",{})
    fr=r["choices"][0].get("finish_reason")
    return {"run":i,"wall":round(wall,1),"in_tok":u.get("prompt_tokens",0),
            "out_tok":u.get("completion_tokens",0),"tg":round(tmg.get("predicted_per_second",0),1),
            "finish":fr,"html_lines":len(html.splitlines()),"js_lines":len(js.splitlines()),
            "js_syntax":syn,"features":"%d/%d"%(len(feats),len(CHECKS)),
            "missing":[n for n,_ in CHECKS if n not in feats]}
if __name__=="__main__":
    n=int(sys.argv[1]) if len(sys.argv)>1 else 3
    rs=[]
    for i in range(1,n+1):
        r=run(i); rs.append(r); print(json.dumps(r,ensure_ascii=False),flush=True)
    print("SUMMARY 總wall=%.0fs 總tok=%d 語法OK=%d/%d"%(
        sum(x["wall"] for x in rs), sum(x["in_tok"]+x["out_tok"] for x in rs),
        sum(1 for x in rs if x["js_syntax"]=="OK"), len(rs)))
