import requests, json
BASE="http://127.0.0.1:8088/v1"
TOOLS=[{"type":"function","function":{"name":"create_ticket",
 "description":"Create a support ticket.",
 "parameters":{"type":"object","properties":{
   "title":{"type":"string"},
   "priority":{"type":"string","enum":["low","normal","high","urgent"]},
   "labels":{"type":"array","items":{"type":"string"}},
   "assignee":{"type":"object","properties":{
       "team":{"type":"string","enum":["infra","frontend","billing"]},
       "user":{"type":"string"}},"required":["team"]},
   "due_days":{"type":"integer","minimum":1,"maximum":30},
   "notify":{"type":"boolean"}},
  "required":["title","priority","assignee"]}}},
 {"type":"function","function":{"name":"search_logs",
 "description":"Search application logs.",
 "parameters":{"type":"object","properties":{
   "query":{"type":"string"},
   "level":{"type":"string","enum":["debug","info","warn","error"]},
   "since_minutes":{"type":"integer"}},"required":["query"]}}}]

CASES=[
 ("結帳頁面在行動裝置上會白畫面，很急，指派給 frontend 團隊的 alice，三天內處理，要通知。標籤加 mobile 跟 checkout。","create_ticket",
   lambda a: a.get("priority")=="urgent" and a.get("assignee",{}).get("team")=="frontend"
             and a.get("assignee",{}).get("user")=="alice" and a.get("due_days")==3
             and a.get("notify") is True and set(a.get("labels",[]))=={"mobile","checkout"}),
 ("幫我查過去 15 分鐘 payment gateway 的錯誤日誌","search_logs",
   lambda a: a.get("level")=="error" and a.get("since_minutes")==15 and "payment" in a.get("query","").lower()),
 ("開一張單給 billing 團隊，標題「發票重複開立」，優先度普通","create_ticket",
   lambda a: a.get("priority")=="normal" and a.get("assignee",{}).get("team")=="billing"),
 ("infra 那邊的磁碟快滿了，開高優先度的單，不用通知","create_ticket",
   lambda a: a.get("priority")=="high" and a.get("assignee",{}).get("team")=="infra" and a.get("notify") is False),
 ("查一下 timeout 相關的 warn 等級 log","search_logs",
   lambda a: a.get("level")=="warn" and "timeout" in a.get("query","").lower()),
 ("Create a low priority ticket titled 'Update README' for the infra team, due in 30 days","create_ticket",
   lambda a: a.get("priority")=="low" and a.get("due_days")==30 and a.get("assignee",{}).get("team")=="infra"),
 ("登入 API 一直 500，開緊急單給 infra 的 bob，標籤 auth，兩天內","create_ticket",
   lambda a: a.get("priority")=="urgent" and a.get("assignee",{}).get("user")=="bob"
             and a.get("due_days")==2 and "auth" in a.get("labels",[])),
 ("搜尋最近一小時所有 info 以上的 database 連線紀錄","search_logs",
   lambda a: "database" in a.get("query","").lower() and a.get("since_minutes")==60),
]
ok=valid=total=0
fails=[]
REPS=3
for rep in range(REPS):
    for prompt, want_fn, check in CASES:
        total+=1
        r=requests.post(BASE+"/chat/completions", json={"model":"qwen3.8-27b",
          "messages":[{"role":"system","content":"You are an ops assistant. Use the tools. Do not ask clarifying questions."},
                      {"role":"user","content":prompt}],
          "tools":TOOLS,"tool_choice":"auto","temperature":0.7,"top_p":0.8,
          "max_tokens":1500,"reasoning_effort":"low"}, timeout=600).json()
        m=r["choices"][0]["message"]
        tcs=m.get("tool_calls") or []
        if not tcs: fails.append((prompt[:22],"no_tool_call")); continue
        tc=tcs[0]
        try: args=json.loads(tc["function"]["arguments"])
        except Exception: fails.append((prompt[:22],"bad_json")); continue
        valid+=1
        if tc["function"]["name"]!=want_fn:
            fails.append((prompt[:22],"wrong_fn:"+tc["function"]["name"])); continue
        if check(args): ok+=1
        else: fails.append((prompt[:22],"wrong_args:"+json.dumps(args,ensure_ascii=False)[:110]))
print(f"總計 {total} 次  JSON/schema 合法 {valid} ({100*valid/total:.1f}%)  語意完全正確 {ok} ({100*ok/total:.1f}%)")
for f in fails: print("  MISS", f[0], "->", f[1])
