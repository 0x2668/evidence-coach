#!/usr/bin/env python3
"""Run the scenarios in tests/scenarios.md against the evidence-coach agent.

Each scenario's prompt is sent as one message to `claude -p --agent evidence-coach`.
Write, Edit, web tools and the Strava and Google Calendar connectors are
blocked so that no test reads or stores real athlete data; Bash is allowed only
for the activity summary script. Responses go to tests/results/round-N/<ID>.md
with mechanical checks (cited claim IDs exist, no emojis); scoring is manual.

With --via-skill the prompt is sent as /evidence-coach <prompt> in a normal
session instead, the route used after installing with npx skills.

Usage: python3 tests/run_scenarios.py --round 1 [--only S01 S04] [--jobs 4] [--via-skill] [--model sonnet] [--runs 5]

With --runs N above 1, each scenario runs N times and each reply is saved as
<ID>-run<k>.md, because one pass says little about a model that varies.
"""
import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SCENARIOS = PROJECT / "tests" / "scenarios.md"
BLOCKED = ["Write", "Edit", "NotebookEdit", "WebSearch", "WebFetch", "mcp__claude_ai_Strava", "mcp__claude_ai_Google_Calendar"]
ALLOWED = ["Read", "Grep", "Glob", "Bash(python3 *activity_summary.py *)"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌]")
CLAIM = re.compile(r"\b[A-Z]{3}-\d{2,3}\b")


def scenarios():
    text = SCENARIOS.read_text(encoding="utf-8")
    out = {}
    for block in re.split(r"^## (?=S\d\d:)", text, flags=re.M)[1:]:
        sid, title = block.split("\n", 1)[0].split(": ", 1)
        prompt = re.search(r"Prompt:\n```text\n(.*?)\n```", block, re.S).group(1)
        out[sid] = (title.strip(), prompt)
    return out


def known_claims():
    return {json.loads(l)["id"] for f in (PROJECT / "skills" / "evidence-coach" / "research" / "claims").glob("*.jsonl")
            for l in f.read_text(encoding="utf-8").splitlines() if l.strip()}


def run_one(sid, title, prompt, outdir, claims, via_skill=False, model="sonnet", run=None):
    route = ["-p", f"/evidence-coach {prompt}"] if via_skill else ["-p", prompt, "--agent", "evidence-coach"]
    cmd = ["claude", *route, "--model", model, "--output-format", "json", "--no-session-persistence",
           # A personal skill of the same name outranks the project's, so without this an
           # installed copy of the skill would be tested instead of this repository's.
           "--setting-sources", "project,local",
           "--disallowedTools", *BLOCKED, "--allowedTools", *ALLOWED]
    proc = subprocess.run(cmd, cwd=PROJECT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {"result": f"(no JSON output)\nstdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}"}
    reply = data.get("result", "")
    cited = sorted(set(CLAIM.findall(reply)))
    unknown = [c for c in cited if c not in claims]
    emojis = sorted(set(EMOJI.findall(reply)))
    models = ", ".join(data.get("modelUsage", {}) or []) or "?"
    cost = data.get("total_cost_usd")
    checks = (f"- cited claim IDs: {len(cited)}; unknown: {', '.join(unknown) or 'none'}\n"
              f"- emojis: {' '.join(emojis) or 'none'}\n"
              f"- turns: {data.get('num_turns')}; models: {models}; error: {data.get('is_error')}")
    name = f"{sid}-run{run}" if run else sid
    (outdir / f"{name}.md").write_text(f"# {sid}: {title}\n\n## Prompt\n\n{prompt}\n\n## Mechanical checks\n\n{checks}\n\n"
                                      f"## Response\n\n{reply}\n", encoding="utf-8")
    return name, cost, unknown, emojis, data.get("is_error") is not False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--via-skill", action="store_true")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--runs", type=int, default=1)
    a = ap.parse_args()
    todo = {k: v for k, v in scenarios().items() if not a.only or k in a.only}
    outdir = PROJECT / "tests" / "results" / f"round-{a.round}"
    outdir.mkdir(parents=True, exist_ok=True)
    claims = known_claims()
    with ThreadPoolExecutor(a.jobs) as pool:
        runs = range(1, a.runs + 1) if a.runs > 1 else [None]
        jobs = [pool.submit(run_one, sid, t, p, outdir, claims, a.via_skill, a.model, r)
                for sid, (t, p) in todo.items() for r in runs]
        for j in jobs:
            name, cost, unknown, emojis, failed = j.result()
            print(f"{name}: cost {cost}; unknown IDs {unknown or 'none'}; emojis {emojis or 'none'}"
                  f"{'; RUN FAILED' if failed else ''}", flush=True)


if __name__ == "__main__":
    main()
