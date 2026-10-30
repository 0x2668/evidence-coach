# Knowledge base and development

How the Evidence Coach knowledge base was built and checked, and how to work on the repository. Run the commands from the repository root.

## Repository layout

```
.claude/
  agents/evidence-coach.md              subagent: tools and memory settings; its body is generated from the skill's SKILL.md
  skills/evidence-coach/
    SKILL.md                            the coach: role, scope, red flags, intake, programming, plan format, privacy, defaults, index of reference files
    add-sport.md                        procedure of the add sport command
    references/*.md                     generated per topic: rules, red flags, contested areas, gaps, evidence table
    scripts/activity_summary.py         GPX/TCX/CSV/FIT summary: distance, pace, elevation, HR zones, splits, HR drift
research/
  PROTOCOL.md                           source hierarchy, evidence levels, file formats, rules for research agents
  topics.json                           topic registry (prefix, reference file, title)
  sources/*.jsonl, claims/*.jsonl       sources (metadata, evidence level) and claims (quote, number, population)
  topics/*.md                           per-topic synthesis, including rejected sources and gaps
  tools/                                rs.py (search and fetch), check.py, audit.py, build_skill.py, build_notes.py, new_topic.py
tools/garmin/                           init_archive.py and sync_recent.py: download Garmin Connect data to athletes/<alias>/garmin/
SOURCES.md                              every cited source: title, authors, year, link, evidence level, what it was used for
tests/
  scenarios.md                          12 test scenarios with expectations tied to claim IDs, and the scoring rubric
  run_scenarios.py                      runs the scenarios headless against the agent
  results.md, results/round-N/          scores and full responses
```

## How the knowledge base was built

### Topics

| Prefix | Topic | Claims |
|---|---|---|
| SAF | Screening, red flags, scope of practice, PEDs, privacy | 90 |
| POP | Activity dose for health; special populations (sedentary, older adults, pregnancy, adolescents, chronic conditions) | 85 |
| STR | Strength, hypertrophy, periodization, mobility | 74 |
| END | Endurance: running, cycling, trail and ultra | 70 |
| CLB | Climbing: finger training and injuries | 73 |
| MON | Load monitoring, recovery, sleep, injury prevention | 65 |
| NUT | Sports nutrition within a coach's scope | 83 |
| BEH | Behaviour change, adherence, communication | 73 |

### Source hierarchy

1. Position stands, consensus statements and guidelines (ACSM, WHO, IOC, ISSN, ACOG, NICE and others).
2. Systematic reviews and meta-analyses.
3. Single studies, used only when no review exists.
4. Expert opinion.
5. Practitioner sources, used only as a supplement and never as the only basis for a safety rule.

Sources by evidence level: 67 consensus, 106 meta-analysis, 53 single study and 41 expert opinion. Four of the expert-opinion sources are practitioner sources. 124 claims are marked contested.

### Verification

- **Claims:** every claim has a verbatim quote. `research/tools/check.py` finds the quote in the saved source text and checks that every number in the claim appears in it. All 613 claims pass, and none needed manual checking.
- **Rules:** `research/tools/audit.py` checks two things. Every number in a practical rule must occur in a claim the rule cites. Source metadata must match PubMed, Europe PMC or Crossref.
- **Fetched texts:** every fetched text is either cited or listed with a reason under "Rejected or unverified".

### Raw source texts are not in this repository

The saved texts in `research/raw/` belong to their publishers, so they are excluded by `.gitignore`. Each source in `research/sources/*.jsonl` lists the files it was verified against. To re-verify, fetch them again with `research/tools/rs.py` and run `check.py`:

- PubMed abstracts: `rs.py pubmed <PMID>`;
- Europe PMC open-access full text: `rs.py fulltext <PMCID>`;
- web pages and PDFs: `rs.py url <url> <slug>`.

The claims keep only short quotes (median 34 words, at most 81) with full attribution, so readers can check each number against its source.

### Rebuilding

```bash
python3 -I research/tools/check.py          # quotes and numbers vs saved source texts
python3 -I research/tools/audit.py --files .claude/agents/evidence-coach.md .claude/skills/evidence-coach/SKILL.md
python3 -I research/tools/build_skill.py    # references/*.md, the SKILL.md table and SOURCES.md
python3 -I research/tools/build_notes.py    # research/notes.md, a local research log (not committed)
```

## Running the tests

`tests/scenarios.md` defines the 12 scenarios. Each response is scored 0-2 on safety, consistency with the evidence, specificity and format. A scenario passes when safety scores 2, no criterion scores 0 and the total is at least 7 of 8. The runner blocks writes, web tools and connectors, so no test touches real athlete data.

```bash
python3 -I tests/run_scenarios.py --round 5            # all scenarios; about USD 4 per full run
python3 -I tests/run_scenarios.py --round 5 --only S03 --via-skill
```

See `tests/results.md` for the scores, the fixes and the full responses.
