#!/usr/bin/env python3
"""Generate the skill's references/*.md and the project's SOURCES.md from research/.

Each reference file keeps a topic's practical rules, red flags, contested areas
and evidence gaps (not the "Rejected" section) and ends with an evidence table
mapping every cited claim ID to its source, year, evidence level and link.
SOURCES.md lists every source cited by the reference files. The "Read this file"
table in SKILL.md is rewritten from research/topics.json, and the body of the
evidence-coach agent is rewritten from SKILL.md (the skills field does not preload a
skill when the agent runs with --agent, so the agent carries its own copy).

Usage: python3 research/tools/build_skill.py
"""
import importlib.util
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # research/
PROJECT = ROOT.parent
_spec = importlib.util.spec_from_file_location("check", Path(__file__).with_name("check.py"))
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)
SKILL = PROJECT / ".claude" / "skills" / "evidence-coach" / "SKILL.md"
REFS = SKILL.parent / "references"
AGENT = PROJECT / ".claude" / "agents" / "evidence-coach.md"
FILES = {t["prefix"]: (t["file"], t["title"]) for t in check.TOPICS}
TABLE_START, TABLE_END = "<!-- reference table: generated from research/topics.json -->", "<!-- end of reference table -->"
KEEP = {"practical rules": "Practical rules", "red flags": "Red flags and referral triggers",
        "contested": "Contested areas", "gaps": "Evidence gaps"}
REF = check.REF


def rows(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def sections(md):
    """Split a topic file into (heading, body) pairs at '## ' headings."""
    out, head, buf = [], None, []
    for line in md.splitlines():
        if line.startswith("## "):
            if head:
                out.append((head, "\n".join(buf).strip()))
            head, buf = line[3:].strip(), []
        elif head:
            buf.append(line)
    if head:
        out.append((head, "\n".join(buf).strip()))
    return out


def cell(v):
    return str(v).replace("|", "/").replace("\n", " ").strip()


def link(s):
    return f"https://doi.org/{s['doi']}" if s.get("doi") else s["url"]


def write_skill_table():
    text = SKILL.read_text(encoding="utf-8")
    head, found_start, rest = text.partition(TABLE_START)
    _, found_end, tail = rest.partition(TABLE_END)
    if not (found_start and found_end):
        print("SKILL.md: reference table markers not found; table not updated")
        return
    table = ["| Read this file | When |", "|---|---|"] + [f"| `references/{t['file']}` | {t['when']} |" for t in check.TOPICS]
    SKILL.write_text(head + TABLE_START + "\n" + "\n".join(table) + "\n" + TABLE_END + tail, encoding="utf-8")
    print(f"wrote SKILL.md reference table: {len(table) - 2} files")


def write_agent():
    _, front, _ = AGENT.read_text(encoding="utf-8").split("---\n", 2)
    _, _, body = SKILL.read_text(encoding="utf-8").split("---\n", 2)
    body = body[body.index("# Role"):]
    skill_dir = ".claude/skills/" + SKILL.parent.name
    body = body.replace("<this skill's directory>", skill_dir).replace("this skill's `references/` directory", f"`{skill_dir}/references/`")
    note = f"<!-- Generated from {skill_dir}/SKILL.md by research/tools/build_skill.py; edit that file. -->"
    AGENT.write_text("---\n" + front + "---\n\n" + note + "\n\n" + body, encoding="utf-8")
    print("wrote agents/evidence-coach.md from SKILL.md")


def main():
    claims = {c["id"]: c for f in (ROOT / "claims").glob("*.jsonl") for c in rows(f)}
    sources = {}
    for f in sorted((ROOT / "sources").glob("*.jsonl")):
        for s in rows(f):
            sources.setdefault(s["key"], s)
    REFS.mkdir(parents=True, exist_ok=True)
    used_for = defaultdict(set)
    for p, (fname, title) in FILES.items():
        topic = ROOT / "topics" / f"{p}.md"
        if not topic.exists():
            print(f"skip {p}: no topic file")
            continue
        parts = [f"# {title}", "",
                 "Evidence levels: consensus, meta-analysis, single study, expert opinion. "
                 "IDs in brackets, such as [STR-05], point to the evidence table at the end of this file. "
                 f"Generated from the verified research notes on {date.today().isoformat()}; do not edit by hand.", ""]
        cited = []
        for head, body in sections(topic.read_text(encoding="utf-8")):
            key = next((k for k in KEEP if head.lower().startswith(k)), None)
            if key and body:
                parts += [f"## {KEEP[key]}", "", body, ""]
                cited += REF.findall(body)
        ids = sorted(set(cited), key=lambda x: (x[:3] != p, x))
        missing = [i for i in ids if i not in claims]
        parts += ["## Evidence table", "", "| ID | Source | Year | Level | Population | Link |", "|---|---|---|---|---|---|"]
        for i in ids:
            if i not in claims:
                continue
            c = claims[i]
            s = sources[c["source"]]
            authors = s["authors"].split(", ")
            who = s["authors"] if len(s["authors"]) < 40 else authors[0] + " et al."
            level = s["level"] + (" (practitioner)" if s.get("practitioner") else "")
            parts.append(f"| {i} | {cell(who)}: {cell(s['title'])[:90]} | {s['year']} | {level} | "
                         f"{cell(c.get('population', ''))[:90]} | {link(s)} |")
            used_for[c["source"]].add(cell(c["used_for"]))
        (REFS / fname).write_text("\n".join(parts) + "\n", encoding="utf-8")
        print(f"wrote {fname}: {len(ids)} cited claims" + (f"; unknown IDs {missing}" if missing else ""))

    out = ["# Sources", "",
           f"Every source cited in `.claude/skills/evidence-coach/references/`. Generated from `research/` on {date.today().isoformat()}.",
           "Evidence levels: consensus (position stand, consensus statement or guideline), meta-analysis (systematic review "
           "with or without meta-analysis), single study, expert opinion (narrative review, Delphi, textbook, practitioner). "
           "Practitioner sources are supplementary only.", "",
           "| Title | Authors | Year | Link | Evidence level | Used for |", "|---|---|---|---|---|---|"]
    for key in sorted(used_for, key=lambda k: (sources[k]["authors"].lower(), sources[k]["year"])):
        s = sources[key]
        level = s["level"] + (" (practitioner)" if s.get("practitioner") else "")
        if s.get("superseded"):
            level += f"; superseded by {s['superseded']}"
        uses = "; ".join(sorted(used_for[key]))
        out.append(f"| {cell(s['title'])} | {cell(s['authors'])} | {s['year']} | {link(s)} | {level} | {cell(uses)} |")
    (PROJECT / "SOURCES.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote SOURCES.md: {len(used_for)} sources")
    write_skill_table()
    write_agent()


if __name__ == "__main__":
    main()
