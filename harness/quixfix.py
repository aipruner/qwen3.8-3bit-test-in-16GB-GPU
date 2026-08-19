#!/usr/bin/env python3
"""Run the local ReAct agent against QuixBugs (Lin et al., 2017) Python defects.

QuixBugs: 40 single-line-defect programs from the Quixey Challenge.
https://github.com/jkoppel/QuixBugs  (MIT)
We use the 31 programs that ship JSON test cases (pure functions).
"""
import json, os, shutil, subprocess, sys, time, hashlib, argparse
import requests

BASE = os.environ.get("QWEN_URL", "http://127.0.0.1:8088/v1")
MODEL = "qwen3.8-27b"
HERE = os.path.dirname(os.path.abspath(__file__))
QB = os.path.abspath(os.path.join(HERE, "..", "QuixBugs-master"))
OUT = os.path.join(HERE, os.environ.get("QUIX_OUT", "quix_runs"))

# programs needing list() around the result (matches upstream pytest files)
NEEDS_LIST = {"flatten", "kheapsort"}
# sqrt is compared with a tolerance equal to the epsilon argument
APPROX = {"sqrt"}
# hanoi returns a list of tuples; the JSON fixtures store lists
TUPLES = {"hanoi"}
# upstream marks these "slow": even the reference fix is exponential and blows the
# 25s budget, so the suite cannot discriminate a fix from a non-fix. Excluded.
SKIP = {"knapsack", "levenshtein"}

TESTTMPL = '''import unittest, json
from {name} import {name}

CASES = json.loads(r"""{cases}""")

class T(unittest.TestCase):
    def test_all(self):
        for i, (inp, exp) in enumerate(CASES):
            got = {call}
            {assertion}
'''

TOOLS = [
    {"type": "function", "function": {
        "name": "list_dir", "description": "List files in a directory of the project.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative path, use '.' for project root"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a text file from the project.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative file path"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "Overwrite a file with new content.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "run_tests", "description": "Run the unit test suite and return the output.",
        "parameters": {"type": "object", "properties": {}}}},
]

SYSTEM = ("You are a coding agent working inside a small Python project. "
          "Use the provided tools to inspect files, fix the bug, and verify with run_tests. "
          "Do not guess file contents: read them. "
          "When all tests pass, reply with the single word DONE and a one-sentence summary.")
TASK = ("The test suite is failing. Find the root cause, fix it in the source "
        "(not in the tests), and keep fixing until run_tests reports OK.")


def build(name, work):
    os.makedirs(work, exist_ok=True)
    src = open(os.path.join(QB, "python_programs", name + ".py")).read()
    # strip the trailing docstring block: it is the spec, keep it (upstream ships it)
    open(os.path.join(work, name + ".py"), "w").write(src)
    cases = [json.loads(l) for l in open(os.path.join(QB, "json_testcases", name + ".json"))]
    if name in NEEDS_LIST:
        call = "list(%s(*inp))" % name
    elif name in TUPLES:
        call = "[list(t) for t in %s(*inp)]" % name
    else:
        call = "%s(*inp)" % name
    if name in APPROX:
        assertion = "self.assertAlmostEqual(got, exp, delta=inp[-1], msg='case %d' % i)"
    else:
        assertion = "self.assertEqual(got, exp, 'case %d' % i)"
    open(os.path.join(work, "test_" + name + ".py"), "w").write(
        TESTTMPL.format(name=name, cases=json.dumps(cases), call=call, assertion=assertion))


def run_suite(work, name, timeout=10):
    try:
        r = subprocess.run([sys.executable, "-m", "unittest", "test_" + name],
                           cwd=work, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        return "TIMEOUT: the test run exceeded %ds (likely an infinite loop)." % timeout


def passed(work, name):
    out = run_suite(work, name)
    lines = [l for l in out.splitlines() if l.strip()]
    return bool(lines) and lines[-1].startswith("OK")


def exec_tool(work, name, prog, args):
    try:
        if name == "list_dir":
            return "\n".join(sorted(os.listdir(os.path.join(work, args.get("path", ".")))))
        if name == "read_file":
            return open(os.path.join(work, args["path"])).read()
        if name == "write_file":
            open(os.path.join(work, args["path"]), "w").write(args["content"])
            return "written %d bytes" % len(args["content"])
        if name == "run_tests":
            return run_suite(work, prog)
        return "unknown tool: " + name
    except Exception as e:
        return "TOOL ERROR: %s: %s" % (type(e).__name__, e)


def one(prog, effort, max_steps=14):
    work = os.path.join(OUT, prog)
    shutil.rmtree(work, ignore_errors=True)
    build(prog, work)
    tpath = os.path.join(work, "test_" + prog + ".py")
    thash = hashlib.md5(open(tpath, "rb").read()).hexdigest()

    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": TASK}]
    m = dict(steps=0, tool_calls=0, bad_calls=0, in_tok=0, out_tok=0, gen_tok=0, gen_s=0.0)
    t0 = time.time()
    for _ in range(max_steps):
        m["steps"] += 1
        body = {"model": MODEL, "messages": msgs, "tools": TOOLS,
                "temperature": 0.7, "top_p": 0.8, "max_tokens": 3000,
                "reasoning_effort": effort}
        r = requests.post(BASE + "/chat/completions", json=body, timeout=3600).json()
        if "choices" not in r:
            break
        u = r.get("usage", {}) or {}
        m["in_tok"] += u.get("prompt_tokens", 0); m["out_tok"] += u.get("completion_tokens", 0)
        tm = r.get("timings") or {}
        if tm.get("predicted_per_second"):
            m["gen_tok"] += tm.get("predicted_n", 0); m["gen_s"] += tm.get("predicted_ms", 0) / 1000.0
        msg = r["choices"][0]["message"]
        msgs.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
        tcs = msg.get("tool_calls") or []
        if not tcs:
            break
        for tc in tcs:
            m["tool_calls"] += 1
            try:
                a = json.loads(tc["function"]["arguments"])
            except Exception:
                a = {}; m["bad_calls"] += 1
            msgs.append({"role": "tool", "tool_call_id": tc["id"],
                         "content": exec_tool(work, tc["function"]["name"], prog, a)[:3000]})
    m["wall"] = time.time() - t0
    m["cheated"] = hashlib.md5(open(tpath, "rb").read()).hexdigest() != thash
    m["passed"] = passed(work, prog) and not m["cheated"]
    m["tg"] = m["gen_tok"] / m["gen_s"] if m["gen_s"] else 0.0
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    progs = sorted(f[:-5] for f in os.listdir(os.path.join(QB, "json_testcases")))
    progs = [p for p in progs if p not in SKIP]
    if a.only:
        progs = [p for p in progs if p in a.only.split(",")]
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for p in progs:
        r = one(p, a.effort); r["prog"] = p; rows.append(r)
        print("%-28s %s steps=%-3d calls=%-3d out_tok=%-6d %5.1fs tg=%5.1f %s" % (
            p, "PASS" if r["passed"] else "FAIL", r["steps"], r["tool_calls"],
            r["out_tok"], r["wall"], r["tg"], "CHEAT" if r["cheated"] else ""), flush=True)
    ok = sum(r["passed"] for r in rows)
    print("\nSUMMARY %d/%d passed  total_wall=%.0fs  total_tok=%d (in %d / out %d)  calls=%d bad=%d cheat=%d" % (
        ok, len(rows), sum(r["wall"] for r in rows),
        sum(r["in_tok"] + r["out_tok"] for r in rows), sum(r["in_tok"] for r in rows),
        sum(r["out_tok"] for r in rows), sum(r["tool_calls"] for r in rows),
        sum(r["bad_calls"] for r in rows), sum(r["cheated"] for r in rows)))
    json.dump(rows, open(os.path.join(OUT, "results.json"), "w"), indent=1)
