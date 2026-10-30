#!/usr/bin/env python3
"""Run the scenarios in tests/scenarios.md against the ai-coach agent.

Each scenario's prompt is sent as one message to `claude -p --agent ai-coach`.
Write, Edit, web tools and the Strava and Google Calendar connectors are
blocked so that no test reads or stores real athlete data; Bash is allowed only
for the activity summary script. Responses go to tests/results/round-N/<ID>.md
with mechanical checks (cited claim IDs exist, no emojis); scoring is manual.

Usage: python3 tests/run_scenarios.py --round 1 [--only S01 S04] [--jobs 4]
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
ALLOWED = ["Read", "Grep", "Glob", "Bash(python3 .claude/skills/training-knowledge/scripts/activity_summary.py *)"]
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
    return {json.loads(l)["id"] for f in (PROJECT / "research" / "claims").glob("*.jsonl")
            for l in f.read_text(encoding="utf-8").splitlines() if l.strip()}


def run_one(sid, title, prompt, outdir, claims):
    cmd = ["claude", "-p", prompt, "--agent", "ai-coach", "--output-format", "json", "--no-session-persistence",
           "--disallowedTools", *BLOCKED, "--allowedTools", *ALLOWED]
    proc = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=900)
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
              f"- turns: {data.get('num_turns')}; cost USD: {cost}; models: {models}; error: {data.get('is_error')}")
    (outdir / f"{sid}.md").write_text(f"# {sid}: {title}\n\n## Prompt\n\n{prompt}\n\n## Mechanical checks\n\n{checks}\n\n"
                                      f"## Response\n\n{reply}\n", encoding="utf-8")
    return sid, cost, unknown, emojis


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    todo = {k: v for k, v in scenarios().items() if not a.only or k in a.only}
    outdir = PROJECT / "tests" / "results" / f"round-{a.round}"
    outdir.mkdir(parents=True, exist_ok=True)
    claims = known_claims()
    with ThreadPoolExecutor(a.jobs) as pool:
        jobs = [pool.submit(run_one, sid, t, p, outdir, claims) for sid, (t, p) in todo.items()]
        for j in jobs:
            sid, cost, unknown, emojis = j.result()
            print(f"{sid}: cost {cost}; unknown IDs {unknown or 'none'}; emojis {emojis or 'none'}", flush=True)


if __name__ == "__main__":
    main()
