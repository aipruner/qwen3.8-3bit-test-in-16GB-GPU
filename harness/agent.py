#!/usr/bin/env python3
"""Minimal ReAct agent harness against a local OpenAI-compatible endpoint."""
import json, os, shutil, subprocess, sys, time, argparse

BASE = os.environ.get("QWEN_URL", "http://127.0.0.1:18038/v1").rstrip("/")
MODEL = "qwen3.8-27b"
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "proj_template")
TESTMOD = "test_cart"

import requests

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


def exec_tool(work, name, args):
    try:
        if name == "list_dir":
            p = os.path.join(work, args.get("path", "."))
            return "\n".join(sorted(os.listdir(p)))
        if name == "read_file":
            with open(os.path.join(work, args["path"])) as f:
                return f.read()
        if name == "write_file":
            with open(os.path.join(work, args["path"]), "w") as f:
                f.write(args["content"])
            return "written %d bytes" % len(args["content"])
        if name == "run_tests":
            r = subprocess.run([sys.executable, "-m", "unittest", TESTMOD],
                               cwd=work, capture_output=True, text=True, timeout=60)
            return (r.stdout + r.stderr)[-2000:]
        return "unknown tool: %s" % name
    except Exception as e:
        return "TOOL ERROR: %s: %s" % (type(e).__name__, e)


def tests_pass(work):
    r = subprocess.run([sys.executable, "-m", "unittest", TESTMOD],
                       cwd=work, capture_output=True, text=True, timeout=60)
    return "OK" in (r.stdout + r.stderr).splitlines()[-1] if (r.stdout + r.stderr).strip() else False


def run(run_id, effort, max_steps=18, outdir="runs"):
    work = os.path.join(os.path.dirname(os.path.abspath(__file__)), outdir, "run%d" % run_id)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(os.path.dirname(work), exist_ok=True)
    shutil.copytree(TEMPLATE, work)

    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": TASK}]
    m = {"steps": 0, "tool_calls": 0, "bad_calls": 0, "tool_errors": 0,
         "in_tok": 0, "out_tok": 0, "wall": 0.0, "gen_tok": 0, "gen_s": 0.0,
         "edited_tests": False, "ran_tests": 0}
    t0 = time.time()
    verdict = "max_steps"

    for step in range(max_steps):
        m["steps"] += 1
        body = {"model": MODEL, "messages": msgs, "tools": TOOLS,
                "temperature": 0.7, "top_p": 0.8, "max_tokens": 3000,
                "reasoning_effort": effort}
        try:
            r = requests.post(BASE + "/chat/completions", json=body, timeout=900)
            d = r.json()
        except Exception as e:
            verdict = "http_error:%s" % e
            break
        if "choices" not in d:
            verdict = "bad_response:%s" % json.dumps(d)[:200]
            break
        ch = d["choices"][0]
        u = d.get("usage", {})
        m["in_tok"] += u.get("prompt_tokens", 0)
        m["out_tok"] += u.get("completion_tokens", 0)
        tm = d.get("timings", {})
        if tm:
            m["gen_tok"] += tm.get("predicted_n", 0)
            m["gen_s"] += tm.get("predicted_ms", 0) / 1000.0
        msg = ch["message"]
        msgs.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})

        tcs = msg.get("tool_calls") or []
        if not tcs:
            txt = (msg.get("content") or "")
            if "DONE" in txt.upper():
                verdict = "declared_done"
            else:
                verdict = "stopped_no_tool"
            break
        for tc in tcs:
            m["tool_calls"] += 1
            fn = tc["function"]["name"]
            raw = tc["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw)
                if not isinstance(args, dict):
                    raise ValueError("not an object")
            except Exception:
                m["bad_calls"] += 1
                msgs.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": "ERROR: arguments were not valid JSON"})
                continue
            if fn == "run_tests":
                m["ran_tests"] += 1
            if fn == "write_file" and TESTMOD in str(args.get("path", "")):
                m["edited_tests"] = True
            out = exec_tool(work, fn, args)
            if out.startswith("TOOL ERROR") or out.startswith("unknown tool"):
                m["tool_errors"] += 1
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": out[:4000]})

    m["wall"] = round(time.time() - t0, 1)
    m["passed"] = tests_pass(work)
    m["verdict"] = verdict
    m["effort"] = effort
    m["tg"] = round(m["gen_tok"] / m["gen_s"], 2) if m["gen_s"] else 0
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--proj", default="proj_template")
    ap.add_argument("--testmod", default="test_cart")
    ap.add_argument("--maxsteps", type=int, default=18)
    ap.add_argument("--tag", default="runs")
    a = ap.parse_args()
    TEMPLATE = os.path.join(HERE, a.proj)
    TESTMOD = a.testmod
    res = []
    for i in range(a.start, a.start + a.runs):
        r = run(i, a.effort, a.maxsteps, a.tag)
        res.append(r)
        print(json.dumps(r), flush=True)
    ok = sum(1 for r in res if r["passed"])
    print("SUMMARY effort=%s pass=%d/%d" % (a.effort, ok, len(res)), flush=True)
