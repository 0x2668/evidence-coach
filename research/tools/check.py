#!/usr/bin/env python3
"""Check research sources and claims.

For every claim: required fields are present, its source exists, its raw file
exists, the quote occurs verbatim in the raw text (after normalising
whitespace, case, dashes and quote marks; "..." may skip text between parts,
which must appear in order), and every number in `number` occurs in the quote.

Usage: python3 research/tools/check.py [--prefix STR] [-v]
Exit status is 1 when any error is found.
"""
import argparse
import functools
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # research/
TOPICS = json.loads((ROOT / "topics.json").read_text(encoding="utf-8"))  # registry; add topics with new_topic.py
PREFIXES = [t["prefix"] for t in TOPICS]
REF = re.compile(r"\b(?:" + "|".join(PREFIXES) + r")-\d{2,3}\b")  # a claim ID such as STR-05
LEVELS = {"consensus", "meta-analysis", "single study", "expert opinion"}
SOURCE_FIELDS = ["key", "title", "authors", "year", "venue", "url", "level", "practitioner", "raw", "meta_verified"]
CLAIM_FIELDS = ["id", "source", "raw", "quote", "claim", "number", "population", "contested", "used_for", "check"]


def norm(s):
    s = unicodedata.normalize("NFKC", s).replace("­", "")
    s = re.sub(r"[‐-―−﹘﹣－]", "-", s)
    s = re.sub(r"[‘’‚‛′`]", "'", s)
    s = re.sub(r"[“”„‟″]", '"', s)
    s = s.replace("×", "x").replace("≥", ">=").replace("≤", "<=")
    return " ".join(s.split()).lower()


def body_of(path):
    """Raw file text after the '# key: value' header block."""
    text = path.read_text(encoding="utf-8", errors="replace")
    head, sep, body = text.partition("\n\n")
    return body if sep and all(l.startswith("# ") for l in head.splitlines()) else text


@functools.lru_cache(maxsize=None)
def bodies_for(path):
    """Normalised raw text, and a fallback without hyphens: PDF line breaks split
    words both as "recom-\\nmended" and "evidence-\\nbased", so the fallback joins
    line-break hyphens and drops all others (the quote is compared without hyphens too)."""
    text = body_of(Path(path))
    return norm(text), norm(re.sub(r"-[ \t]*\n\s*", "", text)).replace("-", "")


def quote_found(quote, body, strip_hyphens=False):
    q = norm(quote)
    if strip_hyphens:
        q = q.replace("-", "")
    pos = 0
    for part in (p.strip() for p in q.split("...")):
        if not part:
            continue
        i = body.find(part, pos)
        if i < 0:
            return False, part
        pos = i + len(part)
    return True, ""


def longest_prefix(part, body):
    """Longest leading piece of `part` found in `body`, to show where a quote diverges."""
    lo, hi = 0, len(part)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if part[:mid] in body:
            lo = mid
        else:
            hi = mid - 1
    return part[:lo]


def load_jsonl(path, errors):
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("not an object")
            rows.append(row)
        except ValueError as e:
            errors.append(f"{path.relative_to(ROOT)}:{n}: invalid JSON ({e})")
    return rows


def check_sources(errors):
    sources = {}
    for f in sorted((ROOT / "sources").glob("*.jsonl")):
        for s in load_jsonl(f, errors):
            where = f"sources/{f.name} [{s.get('key', '?')}]"
            missing = [k for k in SOURCE_FIELDS if k not in s or s[k] in ("", None)]
            if missing:
                errors.append(f"{where}: missing {', '.join(missing)}")
            if s.get("level") not in LEVELS:
                errors.append(f"{where}: level must be one of {sorted(LEVELS)}")
            if not isinstance(s.get("practitioner"), bool):
                errors.append(f"{where}: practitioner must be true/false")
            if not str(s.get("url", "")).startswith("http"):
                errors.append(f"{where}: url must start with http")
            if not re.fullmatch(r"(19|20)\d\d", str(s.get("year", ""))):
                errors.append(f"{where}: year must be a 4-digit year")
            raws = s.get("raw") if isinstance(s.get("raw"), list) else []
            if not isinstance(s.get("raw"), list):
                errors.append(f"{where}: raw must be a list of file names")
            for r in raws:
                if not (ROOT / "raw" / r).exists():
                    errors.append(f"{where}: raw file raw/{r} does not exist")
            key = s.get("key")
            if key in sources:
                prev = sources[key]
                same = norm(str(prev.get("title", ""))).rstrip(" .") == norm(str(s.get("title", ""))).rstrip(" .")
                if not same or str(prev.get("year")) != str(s.get("year")):
                    errors.append(f"{where}: key also used for a different source in sources/{prev['_file']}")
            else:
                sources[key] = {**s, "_file": f.name}
    return sources


def check_claim(c, prefix, sources, seen, errors, warnings):
    """Append problems with one claim to errors/warnings."""
    cid = c.get("id", "?")
    where = f"claims/{prefix}.jsonl [{cid}]"
    missing = [k for k in CLAIM_FIELDS if k not in c or (c[k] in ("", None) and k != "number")]
    if missing:
        errors.append(f"{where}: missing {', '.join(missing)}")
    if not re.fullmatch(rf"{prefix}-\d{{2,3}}", str(cid)):
        errors.append(f"{where}: id must look like {prefix}-01")
    if cid in seen:
        errors.append(f"{where}: duplicate id")
    seen.add(cid)
    if not isinstance(c.get("contested"), bool):
        errors.append(f"{where}: contested must be true/false")
    if c.get("check") not in ("auto", "manual"):
        errors.append(f"{where}: check must be 'auto' or 'manual'")
    src = sources.get(c.get("source"))
    if not src:
        errors.append(f"{where}: unknown source key {c.get('source')!r}")
    elif c.get("raw") not in src.get("raw", []):
        warnings.append(f"{where}: raw {c.get('raw')} is not listed in source {src['key']}'s raw files")
    raw = ROOT / "raw" / str(c.get("raw", ""))
    if not c.get("raw") or not raw.is_file():
        errors.append(f"{where}: raw file raw/{c.get('raw')} not found")
        return
    quote = str(c.get("quote", ""))
    if len(quote.split()) > 80:
        warnings.append(f"{where}: quote is longer than 80 words")
    body, body_nohyphen = bodies_for(str(raw))
    ok, part = quote_found(quote, body)
    if not ok:
        ok = quote_found(quote, body_nohyphen, strip_hyphens=True)[0]
    if not ok:
        hit = longest_prefix(part, body)
        errors.append(f"{where}: quote not found in raw/{c['raw']}\n      matches up to: {hit[-70:]!r}"
                      f"\n      then expected: {part[len(hit):len(hit) + 70]!r}")
        return
    nq = norm(quote)
    for num in re.findall(r"\d+(?:[.,]\d+)?", str(c.get("number", ""))):
        if num not in nq and num.replace(".", ",") not in nq:
            msg = f"{where}: number {num} from 'number' does not occur in the quote"
            if c.get("number_note"):
                warnings.append(f"{msg} (number_note: {c['number_note']})")
            else:
                errors.append(f"{msg}; quote the passage that states it, or add number_note explaining the derivation")


def run(prefix=None):
    """Check everything (or one cluster's claims). Returns a dict of results."""
    errors, warnings = [], []
    sources = check_sources(errors)
    files = [ROOT / "claims" / f"{prefix}.jsonl"] if prefix else sorted((ROOT / "claims").glob("*.jsonl"))
    status, stats, manual, seen = {}, {}, [], set()
    for f in files:
        if not f.exists():
            errors.append(f"claims/{f.name}: file not found")
            continue
        st = stats.setdefault(f.stem, {"claims": 0, "ok": 0, "manual": 0, "failed": 0, "contested": 0})
        for c in load_jsonl(f, errors):
            before = len(errors)
            check_claim(c, f.stem, sources, seen, errors, warnings)
            st["claims"] += 1
            st["contested"] += c.get("contested") is True
            if len(errors) > before:
                status[c.get("id")] = "failed"
            elif c.get("check") == "manual":
                status[c.get("id")] = "manual"
                src = sources.get(c.get("source"), {})
                manual.append(f"{c.get('id')} -> raw/{c.get('raw')} (transcribed; verify against {', '.join(src.get('raw', []))})")
            else:
                status[c.get("id")] = "ok"
            st[status[c.get("id")]] += 1
    return {"errors": errors, "warnings": warnings, "manual": manual, "stats": stats,
            "status": status, "sources": sources}


def report(r, verbose=False):
    by_level = {}
    for s in r["sources"].values():
        by_level.setdefault(str(s.get("level")), []).append(s["key"])
    lines = ["Sources by level: " + (", ".join(f"{k}: {len(v)}" for k, v in sorted(by_level.items())) or "none"),
             f"Practitioner sources: {sum(1 for s in r['sources'].values() if s.get('practitioner') is True)}"]
    for p, st in r["stats"].items():
        lines.append(f"{p}: {st['claims']} claims | quote ok {st['ok']} | manual {st['manual']} | "
                     f"failed {st['failed']} | contested {st['contested']}")
    if r["manual"] and verbose:
        lines += ["", "Needs manual verification (PDF transcriptions):"] + ["  " + m for m in r["manual"]]
    if r["warnings"]:
        lines += ["", f"{len(r['warnings'])} warning(s):"] + ["  " + w for w in r["warnings"]]
    if r["errors"]:
        lines += ["", f"{len(r['errors'])} error(s):"] + ["  " + e for e in r["errors"]]
    else:
        lines += ["", "OK: no errors."]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", choices=PREFIXES)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    r = run(a.prefix)
    print(report(r, verbose=a.verbose or bool(a.prefix)))
    sys.exit(1 if r["errors"] else 0)


if __name__ == "__main__":
    main()
