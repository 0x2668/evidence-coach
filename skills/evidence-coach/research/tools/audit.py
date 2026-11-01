#!/usr/bin/env python3
"""Audit what check.py does not cover.

1. Rules: every number in a topic file line must occur in one of the claims that
   line cites ([PREFIX-NN]); numbers in lines without any citation are listed.
2. Metadata: a source's title, year, PMID and DOI must match the headers of its
   saved raw files (which come from PubMed, Europe PMC or Crossref).
3. Unused raw files: a file saved after a topic was registered with new_topic.py
   must be in some source's `raw` list or be named in that topic file (its
   "Rejected or unverified" section says why it was not used).

Usage: python3 research/tools/audit.py [--prefix STR]
"""
import argparse
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # research/
_spec = importlib.util.spec_from_file_location("check", Path(__file__).with_name("check.py"))
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)
REF = check.REF
NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?")
YEAR = re.compile(r"\b(?:19|20)\d\d\b")


def rows(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def header(path):
    out = {}
    for line in path.read_text(encoding="utf-8", errors="replace").split("\n\n", 1)[0].splitlines():
        if line.startswith("# ") and ": " in line:
            k, v = line[2:].split(": ", 1)
            out[k.strip()] = v.strip()
    return out


SKIP_SECTIONS = ("rejected", "gaps")  # these describe what was left out, not rules


def audit_rules(prefixes, claims):
    problems = []
    for p in prefixes:
        topic = ROOT / "topics" / f"{p}.md"
        if topic.exists():
            problems += audit_file(topic, f"topics/{p}.md", claims, skip_sections=True)
    return problems


def audit_file(path, label, claims, skip_sections=False):
    """Every number in a line must occur in a claim the line cites (frontmatter and code blocks excluded)."""
    problems = []
    skipping, in_code, in_front = False, False, False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip() == "---" and (n == 1 or in_front):
            in_front = n == 1
            continue
        if line.startswith("```"):
            in_code = not in_code
        if in_front or in_code or line.startswith("```"):
            continue
        if skip_sections and line.startswith("## "):
            skipping = line[3:].strip().lower().startswith(SKIP_SECTIONS)
        if skipping or line.lstrip().startswith("#"):
            continue
        refs = REF.findall(line)
        text = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", REF.sub(" ", line))
        text = YEAR.sub(" ", text)
        nums = NUM.findall(text)
        missing_ids = [r for r in refs if r not in claims]
        if missing_ids:
            problems.append(f"{label}:{n}: cites unknown claim(s) {missing_ids}")
        if not nums:
            continue
        if not refs:
            problems.append(f"{label}:{n}: numbers {nums} without any claim citation: {line.strip()[:110]}")
            continue
        hay = check.norm(" ".join(" ".join(str(claims[r].get(k, "")) for k in ("number", "quote", "claim", "caveat", "number_note"))
                                  for r in refs if r in claims))
        absent = [x for x in nums if x not in hay and x.replace(".", ",") not in hay]
        if absent:
            problems.append(f"{label}:{n}: {absent} not found in cited {refs}: {line.strip()[:110]}")
    return problems


def audit_metadata(prefixes):
    problems = []
    for p in prefixes:
        for s in rows(ROOT / "sources" / f"{p}.jsonl"):
            for r in s.get("raw", []):
                path = ROOT / "raw" / r
                if not path.exists() or not r.endswith(".txt") or not r.startswith(("pmid_", "pmc_")):
                    continue
                h = header(path)
                where = f"sources/{p}.jsonl [{s['key']}] vs raw/{r}"
                if h.get("title") and check.norm(h["title"]).rstrip(" .") != check.norm(s.get("title", "")).rstrip(" ."):
                    problems.append(f"{where}: title differs\n      source: {s.get('title', '')[:100]}\n      raw:    {h['title'][:100]}")
                # PubMed's print year is canonical; full-text XML may carry the earlier online year.
                if r.startswith("pmid_") and h.get("year") and str(s.get("year")) != h["year"][:4] and not s.get("year_note"):
                    problems.append(f"{where}: year {s.get('year')} vs raw {h['year']}" +
                                    (f" (epub {h['epub_date']})" if h.get("epub_date") else ""))
                for k in ("pmid", "doi", "pmcid"):
                    if s.get(k) and h.get(k) and str(s[k]).lower() != h[k].lower():
                        problems.append(f"{where}: {k} {s[k]} vs raw {h[k]}")
    return problems


def audit_unused():
    """Raw files saved since a topic was registered: cited by a source, or named in that topic file."""
    started = sorted((datetime.fromisoformat(t["started"]).timestamp(), t["prefix"]) for t in check.TOPICS if t.get("started"))
    if not started:
        return []
    cited = {Path(r).stem for f in (ROOT / "sources").glob("*.jsonl") for s in rows(f) for r in s.get("raw", [])}
    problems = []
    for path in sorted((ROOT / "raw").glob("[!.]*")):
        owners = [p for ts, p in started if ts < path.stat().st_mtime]
        if not owners or path.stem in cited:
            continue
        topic = ROOT / "topics" / f"{owners[-1]}.md"
        if topic.exists() and path.stem in topic.read_text(encoding="utf-8"):
            continue
        problems.append(f"raw/{path.name}: saved after {owners[-1]} was registered, but no source cites it "
                        f"and topics/{owners[-1]}.md does not name it under Rejected")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", choices=check.PREFIXES)
    ap.add_argument("--files", nargs="+", help="also check these Markdown files (e.g. the agent file and SKILL.md)")
    a = ap.parse_args()
    prefixes = [a.prefix] if a.prefix else check.PREFIXES
    claims = {c["id"]: c for f in (ROOT / "claims").glob("*.jsonl") for c in rows(f)}
    checks = [("Rules vs cited claims", audit_rules(prefixes, claims)),
              ("Source metadata vs raw headers", audit_metadata(prefixes)),
              ("Raw files saved for new topics but unused", audit_unused())]
    if a.files:
        checks.append(("Other files vs cited claims",
                       [x for f in a.files for x in audit_file(Path(f), f, claims)]))
    for title, problems in checks:
        print(f"== {title}: {len(problems)} issue(s)")
        for x in problems:
            print("  " + x)


if __name__ == "__main__":
    main()
