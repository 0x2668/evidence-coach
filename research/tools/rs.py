#!/usr/bin/env python3
"""Find sources and save their text verbatim to research/raw/ for quote checking.

Subcommands:
  search   PubMed search, relevance-sorted, with publication types and PMCIDs
  epmc     Europe PMC search (shows which papers have open-access full text)
  pubmed   save title + abstract + metadata for one or more PMIDs
  fulltext save open-access full text (Europe PMC XML) for a PMCID
  doi      Crossref metadata for a DOI, plus the matching PMID
  url      save a web page as plain text; a PDF is converted with pdftotext
           when it is installed, otherwise saved for manual transcription
  pdftext  convert an already saved raw/web_<name>.pdf to text (needs pdftotext)

Standard library only (plus poppler's pdftotext, if present). Requests are
throttled per host across all processes, so several research agents can run
this at the same time.
"""
import argparse
import fcntl
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # research/
RAW = ROOT / "raw"
UA = "Mozilla/5.0 (X11; Linux x86_64) ai-coach-research/1.0"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
TOOL = {"tool": "ai-coach-research"}


def throttle(host, gap):
    """Keep at least `gap` seconds between requests to `host`, across processes."""
    RAW.mkdir(exist_ok=True)
    with open(RAW / f".throttle-{host}", "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # released when the file closes
        f.seek(0)
        try:
            last = float(f.read() or 0)
        except ValueError:
            last = 0.0
        wait = last + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        f.seek(0)
        f.truncate()
        f.write(str(time.time()))


def get(url, params=None, host=None, gap=0.0, tries=6):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(tries):
        if host:
            throttle(host, gap)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(), r.headers.get("Content-Type", ""), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
        except urllib.error.URLError:
            if attempt < tries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def ncbi(endpoint, params):
    return get(EUTILS + endpoint, {**params, **TOOL}, host="ncbi", gap=0.4)[0]


def text_of(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def write_raw(name, header, body):
    path = RAW / name
    lines = [f"# {k}: {v}" for k, v in header.items() if v]
    path.write_text("\n".join(lines) + "\n\n" + body.strip() + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------- search

def cmd_search(a):
    term = a.query
    if a.sr:
        term += " AND (meta-analysis[pt] OR systematic review[pt])"
    if a.guideline:
        term += (" AND (guideline[pt] OR practice guideline[pt] OR consensus development conference[pt]"
                 " OR consensus[ti] OR position stand[ti] OR position statement[ti])")
    if a.since:
        term += f" AND {a.since}:3000[dp]"
    res = json.loads(ncbi("esearch.fcgi", {"db": "pubmed", "term": term, "retmax": a.n,
                                           "retmode": "json", "sort": "relevance"}))["esearchresult"]
    ids = res.get("idlist", [])
    print(f"{res.get('count', 0)} hits for: {term}\nPMID | year | first author | journal | types | PMCID | title")
    if not ids:
        return
    summ = json.loads(ncbi("esummary.fcgi", {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}))["result"]
    for pmid in ids:
        s = summ.get(pmid, {})
        first = (s.get("authors") or [{}])[0].get("name", "?")
        types = ",".join(t for t in s.get("pubtype", []) if t != "Journal Article")
        pmc = next((x["value"] for x in s.get("articleids", []) if x.get("idtype") == "pmc"), "")
        print(f"{pmid} | {(s.get('pubdate') or '')[:4]} | {first} | {s.get('source', '')} | {types} | {pmc} | {s.get('title', '')}")


def cmd_epmc(a):
    params = {"query": a.query, "format": "json", "pageSize": a.n, "resultType": "lite"}
    data = json.loads(get(EPMC + "search", params, host="epmc", gap=0.2)[0])
    print(f"{data.get('hitCount', 0)} hits\nPMID | PMCID | year | first author | journal | OA | title")
    for r in data.get("resultList", {}).get("result", []):
        first = (r.get("authorString") or "?").split(",")[0]
        print(f"{r.get('pmid', '')} | {r.get('pmcid', '')} | {r.get('pubYear', '')} | {first} | "
              f"{r.get('journalTitle', r.get('source', ''))} | {r.get('isOpenAccess', '')} | {r.get('title', '')}")


# ---------------------------------------------------------------- pubmed abstracts

def cmd_pubmed(a):
    root = ET.fromstring(ncbi("efetch.fcgi", {"db": "pubmed", "id": ",".join(a.pmids), "retmode": "xml"}))
    found = set()
    for art in root.findall(".//PubmedArticle"):
        pmid = text_of(art.find("MedlineCitation/PMID"))
        found.add(pmid)
        article = art.find("MedlineCitation/Article")
        pubdate = article.find("Journal/JournalIssue/PubDate")
        year = text_of(pubdate.find("Year")) if pubdate is not None else ""
        if not year and pubdate is not None:
            year = text_of(pubdate.find("MedlineDate"))[:4]
        epub = article.find("ArticleDate")
        epub_date = "-".join(text_of(epub.find(t)) for t in ("Year", "Month", "Day")) if epub is not None else ""
        authors = []
        for au in article.findall("AuthorList/Author"):
            name = f"{text_of(au.find('LastName'))} {text_of(au.find('Initials'))}".strip()
            authors.append(name or text_of(au.find("CollectiveName")))
        ids = {i.get("IdType"): text_of(i) for i in art.findall("PubmedData/ArticleIdList/ArticleId")}
        types = [text_of(t) for t in article.findall("PublicationTypeList/PublicationType")]
        parts = []
        for ab in article.findall("Abstract/AbstractText"):
            label = ab.get("Label")
            parts.append((f"{label}: " if label else "") + text_of(ab))
        title = text_of(article.find("ArticleTitle"))
        header = {
            "source": "pubmed", "pmid": pmid, "doi": ids.get("doi", ""), "pmcid": ids.get("pmc", ""),
            "title": title, "authors": ", ".join(authors),
            "journal": text_of(article.find("Journal/Title")), "year": year, "epub_date": epub_date,
            "publication_types": "; ".join(types),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "fetched": date.today().isoformat(),
        }
        body = f"TITLE: {title}\n\nABSTRACT:\n" + ("\n".join(parts) if parts else "(no abstract in PubMed)")
        path = write_raw(f"pmid_{pmid}.txt", header, body)
        print(f"saved {path.relative_to(ROOT.parent)}\n  {authors[0] if authors else '?'} et al. {year} | "
              f"{header['journal']} | doi {header['doi'] or '-'} | {header['pmcid'] or 'no PMCID'}\n"
              f"  types: {header['publication_types']}\n  {title}")
    for missing in set(a.pmids) - found:
        print(f"PMID {missing}: not found", file=sys.stderr)


# ---------------------------------------------------------------- open-access full text

ATOMIC = {"p", "title", "label", "tr", "def-item", "disp-quote"}


def jats_blocks(el, out):
    if el.tag == "ref-list":
        return
    if el.tag == "tr":
        out.append(" | ".join(text_of(c) for c in el if c.tag in ("td", "th")))
        return
    if el.tag in ATOMIC:
        t = text_of(el)
        if t:
            out.append(t)
        return
    for child in el:
        jats_blocks(child, out)


def print_year(root):
    """Year of the print/collection issue when given, else the first publication date."""
    dates = root.findall(".//article-meta/pub-date")
    for d in dates:
        if d.get("pub-type") in ("ppub", "collection") or d.get("date-type") == "collection" or \
                d.get("publication-format") == "print":
            return text_of(d.find("year"))
    return text_of(dates[0].find("year")) if dates else ""


def cmd_fulltext(a):
    pmcid = a.pmcid.upper()
    pmcid = pmcid if pmcid.startswith("PMC") else "PMC" + pmcid
    try:
        xml = get(EPMC + f"{pmcid}/fullTextXML", host="epmc", gap=0.2)[0]
    except urllib.error.HTTPError as e:
        sys.exit(f"{pmcid}: no open-access full text at Europe PMC (HTTP {e.code}). Use the abstract, "
                 "the publisher's HTML page (rs.py url) or a PDF (manual transcription).")
    root = ET.fromstring(xml)
    meta = root.find(".//article-meta")
    authors = []
    for c in root.findall(".//article-meta/contrib-group/contrib[@contrib-type='author']"):
        sur, given = text_of(c.find("name/surname")), text_of(c.find("name/given-names"))
        initials = "".join(p[0] for p in given.replace("-", " ").split())
        authors.append(f"{sur} {initials}".strip() or text_of(c.find("collab")))
    out = []
    for part in (meta.find("abstract") if meta is not None else None, root.find("body"), root.find("back")):
        if part is not None:
            jats_blocks(part, out)
    title = text_of(root.find(".//article-meta/title-group/article-title"))
    header = {
        "source": "europepmc-fulltext", "pmcid": pmcid,
        "pmid": text_of(root.find(".//article-meta/article-id[@pub-id-type='pmid']")),
        "doi": text_of(root.find(".//article-meta/article-id[@pub-id-type='doi']")),
        "title": title, "authors": ", ".join(authors),
        "journal": text_of(root.find(".//journal-meta//journal-title")),
        "year": print_year(root),
        "url": f"https://europepmc.org/article/PMC/{pmcid}", "fetched": date.today().isoformat(),
    }
    path = write_raw(f"pmc_{pmcid}.txt", header, f"TITLE: {title}\n\n" + "\n".join(out))
    print(f"saved {path.relative_to(ROOT.parent)} ({len(out)} text blocks)\n  {title}")


# ---------------------------------------------------------------- DOI metadata

def cmd_doi(a):
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", a.doi.strip())
    try:
        m = json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(doi), host="crossref", gap=0.1)[0])["message"]
    except urllib.error.HTTPError as e:
        print(f"Crossref: DOI {doi} not found (HTTP {e.code})")
        m = None
    if m:
        def year(k):
            return (m.get(k, {}).get("date-parts") or [[None]])[0][0]
        authors = [f"{x.get('family', '')} {''.join(g[0] for g in x.get('given', '').replace('-', ' ').split())}".strip()
                   or x.get("name", "") for x in m.get("author", [])]
        print(f"Crossref: {(m.get('title') or [''])[0]}\n  authors: {', '.join(authors) or '-'}\n"
              f"  venue: {(m.get('container-title') or [''])[0]} | type: {m.get('type')} | "
              f"print {year('published-print')} | online {year('published-online')} | issued {year('issued')}\n"
              f"  url: https://doi.org/{doi}")
    res = json.loads(ncbi("esearch.fcgi", {"db": "pubmed", "term": f"{doi}[doi]", "retmode": "json"}))["esearchresult"]
    print(f"PubMed PMID(s) for this DOI: {', '.join(res.get('idlist', [])) or 'none'}")


# ---------------------------------------------------------------- web pages

class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
             "table", "ul", "ol", "dd", "dt", "blockquote", "header", "footer", "main", "aside", "caption"}
    SKIP = {"script", "style", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.title, self.in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag in self.BLOCK:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self.in_title = False
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)


def cmd_url(a):
    name = re.sub(r"[^a-z0-9_-]+", "-", a.name.lower()).strip("-")
    try:
        body, ctype, final = get(a.url, host=urllib.parse.urlparse(a.url).hostname, gap=1.0)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} for {a.url}. Try another official copy (PMC, publisher HTML), or WebFetch to locate one.")
    if "pdf" in ctype.lower() or body[:5] == b"%PDF-":
        path = RAW / f"web_{name}.pdf"
        path.write_bytes(body)
        print(f"saved PDF {path.relative_to(ROOT.parent)} ({len(body)} bytes)")
        pdf_to_text(name, a.url)
        return
    charset = re.search(r"charset=([\w-]+)", ctype)
    p = _Text()
    p.feed(body.decode(charset.group(1) if charset else "utf-8", errors="replace"))
    lines = [" ".join(line.split()) for line in "".join(p.out).split("\n")]
    text = "\n".join(line for line in lines if line)
    header = {"source": "web", "title": " ".join(p.title.split()), "url": a.url,
              "final_url": final if final != a.url else "", "content_type": ctype,
              "fetched": date.today().isoformat()}
    path = write_raw(f"web_{name}.txt", header, text)
    print(f"saved {path.relative_to(ROOT.parent)} ({len(text)} chars)\n  title: {header['title']}")
    if len(text) < 1500:
        print("  warning: very little text; the page may need JavaScript or block scripts. Look for another copy.")


def pdf_to_text(name, url=""):
    """raw/web_<name>.pdf -> raw/web_<name>.txt with [page N] markers, if pdftotext is installed."""
    pdf = RAW / f"web_{name}.pdf"
    if not shutil.which("pdftotext"):
        print("  pdftotext is not installed: open the PDF with the Read tool and follow PROTOCOL.md "
              f"'PDF sources' (transcribe into raw/web_{name}.txt, check=manual).")
        return
    # Parsing only; nothing in the PDF is executed.
    res = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, timeout=120)
    if res.returncode != 0:
        print(f"  pdftotext failed: {res.stderr.decode(errors='replace').strip()[:200]}")
        return
    pages = res.stdout.decode("utf-8", errors="replace").split("\f")
    text = "\n".join(f"[page {i}]\n{p.strip()}" for i, p in enumerate(pages, 1) if p.strip())
    header = {"source": "pdf (pdftotext)", "from": pdf.name, "url": url, "fetched": date.today().isoformat()}
    path = write_raw(f"web_{name}.txt", header, text)
    print(f"  converted to {path.relative_to(ROOT.parent)} ({len(pages)} pages, {len(text)} chars); claims can use check=auto")
    if len(text) < 500 * max(1, len(pages) // 4):
        print("  warning: little text for the page count; the PDF may be scanned images. Fall back to manual transcription.")


def cmd_pdftext(a):
    name = re.sub(r"[^a-z0-9_-]+", "-", a.name.lower()).strip("-")
    if not (RAW / f"web_{name}.pdf").exists():
        sys.exit(f"raw/web_{name}.pdf not found")
    pdf_to_text(name, a.url or "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="PubMed search")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=15)
    s.add_argument("--sr", action="store_true", help="only systematic reviews / meta-analyses")
    s.add_argument("--guideline", action="store_true", help="only guidelines / consensus / position stands")
    s.add_argument("--since", type=int, help="publication year from")
    s.set_defaults(fn=cmd_search)
    s = sub.add_parser("epmc", help="Europe PMC search")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=15)
    s.set_defaults(fn=cmd_epmc)
    s = sub.add_parser("pubmed", help="save abstracts for PMIDs")
    s.add_argument("pmids", nargs="+")
    s.set_defaults(fn=cmd_pubmed)
    s = sub.add_parser("fulltext", help="save open-access full text for a PMCID")
    s.add_argument("pmcid")
    s.set_defaults(fn=cmd_fulltext)
    s = sub.add_parser("doi", help="Crossref metadata + PMID for a DOI")
    s.add_argument("doi")
    s.set_defaults(fn=cmd_doi)
    s = sub.add_parser("url", help="save a web page as text")
    s.add_argument("url")
    s.add_argument("name", help="short slug for the file name, e.g. who-2020-guidelines")
    s.set_defaults(fn=cmd_url)
    s = sub.add_parser("pdftext", help="convert a saved raw/web_<name>.pdf to text")
    s.add_argument("name")
    s.add_argument("--url", help="original URL of the PDF, recorded in the header")
    s.set_defaults(fn=cmd_pdftext)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
