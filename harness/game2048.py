import requests, json, re, subprocess, sys, os, time, textwrap
BASE=os.environ.get("QWEN_URL", "http://127.0.0.1:18038/v1").rstrip("/")

SPEC = textwrap.dedent("""\
    請用 Python 實作 2048 的核心邏輯，寫成一個模組。只輸出一個 ```python 程式碼區塊，不要說明文字。

    必須提供這四個函式，簽名完全照寫：

    def slide_left(row):
        '''row 是長度 4 的 list[int]，0 代表空格。回傳 (new_row, gained_score)。
        規則：先把非零往左靠攏，再由左往右合併相鄰的相等值，合併後的格子
        在這一次移動中不能再被合併第二次。gained_score 是本次所有合併結果的總和。'''

    def move(board, direction):
        '''board 是 4x4 的 list[list[int]]，direction 是 'left'/'right'/'up'/'down'。
        回傳 (new_board, gained_score)。不要修改傳入的 board。'''

    def has_moves(board):
        '''還有合法移動就回傳 True，否則 False。'''

    def max_tile(board):
        '''回傳盤面上最大的數字。'''
    """)

TESTS = r'''
import sys, copy
sys.path.insert(0, ".")
from sol import slide_left, move, has_moves, max_tile
R=[]
def chk(name, cond):
    R.append((name, bool(cond)))

# --- slide_left ---
chk("empty",            slide_left([0,0,0,0])[0]==[0,0,0,0])
chk("compact",          slide_left([0,2,0,4])[0]==[2,4,0,0])
chk("simple_merge",     slide_left([2,2,0,0])==( [4,0,0,0], 4))
chk("four_same",        slide_left([2,2,2,2])==( [4,4,0,0], 8))
chk("triple_leftmost",  slide_left([2,2,4,0])==( [4,4,0,0], 4))
chk("no_double_merge",  slide_left([4,4,8,0])==( [8,8,0,0], 8))
chk("gap_merge",        slide_left([2,0,0,2])==( [4,0,0,0], 4))
chk("no_merge_diff",    slide_left([2,4,2,4])==( [2,4,2,4], 0))
chk("big",              slide_left([4,4,4,4])==( [8,8,0,0], 16))
chk("mixed",            slide_left([2,0,2,4])==( [4,4,0,0], 4))

# --- move / immutability ---
b=[[2,2,0,0],[0,0,0,0],[4,0,4,0],[0,0,0,0]]
snap=copy.deepcopy(b)
nb,sc=move(b,"left")
chk("move_left",        nb==[[4,0,0,0],[0,0,0,0],[8,0,0,0],[0,0,0,0]] and sc==12)
chk("no_mutation",      b==snap)
nb,_=move(snap,"right")
chk("move_right",       nb==[[0,0,0,4],[0,0,0,0],[0,0,0,8],[0,0,0,0]])
b2=[[2,0,0,0],[2,0,0,0],[4,0,0,0],[4,0,0,0]]
nb,sc=move(b2,"up")
chk("move_up",          nb[0][0]==4 and nb[1][0]==8 and sc==12)
nb,_=move(b2,"down")
chk("move_down",        nb[3][0]==8 and nb[2][0]==4)

# --- has_moves / max_tile ---
full_stuck=[[2,4,2,4],[4,2,4,2],[2,4,2,4],[4,2,4,2]]
chk("stuck_false",      has_moves(full_stuck) is False)
full_ok=[[2,2,4,8],[4,8,16,32],[2,4,8,16],[4,8,16,32]]
chk("full_but_movable", has_moves(full_ok) is True)
chk("empty_has_moves",  has_moves([[0]*4 for _ in range(4)]) is True)
chk("max_tile",         max_tile([[2,4,0,0],[0,1024,0,0],[0,0,8,0],[0,0,0,0]])==1024)

print(json.__name__ if False else "")
import json as J
print("RESULT " + J.dumps({"passed":sum(1 for _,c in R if c), "total":len(R),
                           "failed":[n for n,c in R if not c]}))
'''

def extract(txt):
    m = re.findall(r"```(?:python)?\s*\n(.*?)```", txt, re.S)
    return m[0] if m else txt

def run(i, effort="medium"):
    work=os.path.join(os.path.dirname(os.path.abspath(__file__)),"game_runs","g%d"%i)
    os.makedirs(work, exist_ok=True)
    t0=time.time()
    r=requests.post(BASE+"/chat/completions", json={"model":"qwen3.8-27b",
        "messages":[{"role":"user","content":SPEC}],
        "max_tokens":6000,"temperature":0.7,"top_p":0.8,"reasoning_effort":effort},
        timeout=1800).json()
    wall=time.time()-t0
    msg=r["choices"][0]["message"]
    code=extract(msg.get("content") or "")
    open(os.path.join(work,"sol.py"),"w").write(code)
    open(os.path.join(work,"t.py"),"w").write(TESTS)
    p=subprocess.run([sys.executable,"t.py"],cwd=work,capture_output=True,text=True,timeout=60)
    out=p.stdout+p.stderr
    m=re.search(r"RESULT (\{.*\})",out)
    res=json.loads(m.group(1)) if m else {"passed":0,"total":19,"failed":["CRASH: "+out.strip().splitlines()[-1][:80]]}
    u=r.get("usage",{}); tmg=r.get("timings",{})
    return {"run":i,"effort":effort,"wall":round(wall,1),
            "in_tok":u.get("prompt_tokens",0),"out_tok":u.get("completion_tokens",0),
            "tg":round(tmg.get("predicted_per_second",0),1),
            "code_lines":len(code.splitlines()),
            "passed":res["passed"],"total":res["total"],"failed":res["failed"]}

if __name__=="__main__":
    eff=sys.argv[1] if len(sys.argv)>1 else "medium"
    n=int(sys.argv[2]) if len(sys.argv)>2 else 5
    allr=[]
    for i in range(1,n+1):
        r=run(i,eff); allr.append(r); print(json.dumps(r,ensure_ascii=False),flush=True)
    tp=sum(x["passed"] for x in allr); tt=sum(x["total"] for x in allr)
    print(f"SUMMARY effort={eff} assertions {tp}/{tt} ({100*tp/tt:.1f}%)  perfect_runs="
          f"{sum(1 for x in allr if x['passed']==x['total'])}/{len(allr)}  "
          f"總wall={sum(x['wall'] for x in allr):.0f}s  總tok={sum(x['in_tok']+x['out_tok'] for x in allr)}")
