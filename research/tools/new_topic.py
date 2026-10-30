#!/usr/bin/env python3
"""Register a new research topic (for example a sport added with /evidence-coach add sport).

Adds the topic to research/topics.json, creates empty sources/<PREFIX>.jsonl and
claims/<PREFIX>.jsonl and a topic file skeleton (PROTOCOL.md section 7), and
records the start time so audit.py can list raw files saved for it but unused.
The other tools read the registry, so check.py, audit.py, build_skill.py and
build_notes.py pick the topic up without further changes.

Usage: python3 research/tools/new_topic.py PREFIX FILE TITLE WHEN
       python3 research/tools/new_topic.py --list
  PREFIX  three capital letters, unused (e.g. SWM)
  FILE    reference file name in the skill (e.g. swimming.md)
  TITLE   heading of the reference file (e.g. "Swimming: training and injuries")
  WHEN    the "When" cell of the SKILL.md table: subjects, comma-separated, no digits
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # research/
REGISTRY = ROOT / "topics.json"
SKELETON = """# {prefix}: {title}

## Practical rules for the agent

## Red flags and referral triggers

## Contested areas

## Rejected or unverified

## Gaps and open questions
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print the registered topics and exit")
    ap.add_argument("prefix", nargs="?")
    ap.add_argument("file", nargs="?")
    ap.add_argument("title", nargs="?")
    ap.add_argument("when", nargs="?")
    a = ap.parse_args()
    topics = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if a.list:
        for t in topics:
            print(f"{t['prefix']}  references/{t['file']}  {t['title']}\n     {t['when']}")
        return
    if not a.when:
        ap.error("PREFIX, FILE, TITLE and WHEN are required")
    problems = []
    if not re.fullmatch(r"[A-Z]{3}", a.prefix):
        problems.append("PREFIX must be three capital letters")
    if any(t["prefix"] == a.prefix for t in topics):
        problems.append(f"prefix {a.prefix} is already registered")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.md", a.file):
        problems.append("FILE must look like swimming.md (lowercase, hyphens)")
    if any(t["file"] == a.file for t in topics):
        problems.append(f"references/{a.file} is already used")
    if re.search(r"\d", a.when):
        problems.append("WHEN must not contain digits (SKILL.md numbers need claim IDs)")
    paths = [ROOT / "sources" / f"{a.prefix}.jsonl", ROOT / "claims" / f"{a.prefix}.jsonl", ROOT / "topics" / f"{a.prefix}.md"]
    problems += [f"{p.relative_to(ROOT)} already exists" for p in paths if p.exists()]
    if problems:
        sys.exit("not registered:\n  " + "\n  ".join(problems))
    topics.append({"prefix": a.prefix, "file": a.file, "title": a.title, "when": a.when,
                   "started": datetime.now(timezone.utc).isoformat(timespec="microseconds")})
    REGISTRY.write_text(json.dumps(topics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    paths[0].touch()
    paths[1].touch()
    paths[2].write_text(SKELETON.format(prefix=a.prefix, title=a.title), encoding="utf-8")
    print(f"registered {a.prefix} -> references/{a.file}; created " + ", ".join(str(p.relative_to(ROOT)) for p in paths))


if __name__ == "__main__":
    main()
