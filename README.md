# Evidence Coach for Claude Code

An evidence-based training coach for [Claude Code](https://code.claude.com/docs). It works in two modes:

- **Coach assistant:** helps a personal trainer with planning, client-week analysis and coaching notes, citing the evidence behind each recommendation.
- **Direct coach:** talks to the athlete, from beginner to advanced.

It covers strength and hypertrophy, running (including trail and ultra), cycling, climbing, and general fitness and mobility. The `/evidence-coach add sport` command adds other sports.

Every number the coach uses comes from a knowledge base of 613 claims from 267 sources. For each claim, a script found the quoted text verbatim in the saved source and checked that every number in the claim appears in the quote. See [how it was built](research/README.md).

> **Not medical advice.** The coach screens for red flags and refers people to clinicians; it does not diagnose or treat. In an emergency, call 112 (EU), 999 (UK) or your local emergency number.

## What it does

- **Safety first.** Every message is checked for red flags before anything else, from "call 112 now" to "continue with modification".
- **Scope of practice.** It does not diagnose or treat, prescribe restrictive diets or advise on medication. It refuses dosing, cycles or "harm reduction" for steroids, SARMs and other performance-enhancing drugs, and explains their risks instead.
- **Intake and plans.** It starts with the PAR-Q+ questions, goals, history and availability. Plans come as a table, with progression rules, a fallback for missed sessions and check-in questions.
- **Evidence-aware answers.** In coach-assistant mode, non-obvious points carry a claim ID and evidence level, for example `[END-34, single study]`. Contested areas are presented as contested, and where the evidence gives no figure, the coach labels its choice as judgement.
- **Training data.** It works with Strava, Garmin Connect, activity files (GPX, TCX, CSV, FIT) and Google Calendar. It writes calendar events only after the person confirms the exact sessions.
- **Privacy.** Health data is a special category under GDPR Article 9. The coach asks only for what it needs, stores nothing without explicit consent, and keeps stored data under an alias in `athletes/<alias>/` or in local agent memory. Both locations are excluded from git.

## Quick start

Requires Claude Code and Python 3 (standard library only).

```bash
git clone https://github.com/0x2668/evidence-coach.git
cd evidence-coach
claude                            # then: "Use the evidence-coach agent: I want to run my first 50 km trail race in 16 weeks..."
claude --agent evidence-coach     # or start a whole session as the coach
```

### Install with `npx skills`

```bash
npx skills add 0x2668/evidence-coach --skill evidence-coach -a claude-code
```

This installs the whole coach as one skill: instructions, knowledge base and activity script. Run it as `/evidence-coach <your question>`, or let Claude load it when you ask about training. `/evidence-coach add sport` and the Garmin scripts work only in a clone.

**Using it in another project:** copy `.claude/skills/evidence-coach/`, plus `.claude/agents/evidence-coach.md` if you want the subagent (edit `SKILL.md`, then rebuild, because the agent's body is a generated copy). Copy `research/` only if you want to extend the knowledge base.

**Connectors:** the agent's `tools` line uses the claude.ai Strava and Google Calendar connectors (`mcp__claude_ai_Strava__*`, `mcp__claude_ai_Google_Calendar__*`). If you use different MCP servers, change those entries in `.claude/agents/evidence-coach.md`. Without connectors, the coach works from what you tell it and from files.

### Add Garmin and Strava data

- **Garmin:** scripts download your history and keep the last 7 days in sync, using Garmin's official Personal API. They store data in `athletes/<alias>/garmin/`. See [`tools/garmin/README.md`](tools/garmin/README.md).
- **Strava connector (recommended for Strava):** connect the claude.ai Strava connector and the coach reads your activities live, after it asks you. It needs an active Strava subscription. Nothing is written to disk unless you ask for it.
- **Strava export:** request your data archive in Strava's account settings, then unpack it into `athletes/<alias>/strava/`.

If your Garmin device already syncs to Strava, you don't need to add the activities twice. Use the Garmin scripts for health data (sleep, HRV, resting HR), which Strava doesn't provide.

### Add a sport

```
/evidence-coach add sport swimming "masters, shoulder pain"
```

This runs the research for one sport in a background subagent and adds a new reference file to the skill. It reports what it found and what it could not verify. Expect 12-20 sources and 30-60 claims.

## Tests

All 12 test scenarios, such as chest pain during intervals, a 1000 kcal crash diet and a SARMs dosing question, pass through the agent. The safety scenarios also pass through `/evidence-coach`. See [`tests/results.md`](tests/results.md) for the scores and [`research/README.md`](research/README.md#running-the-tests) to run them.

## Limitations

- **Populations:** many studies are in young, trained men. The coach says so when it applies them to other groups.
- **Evidence gaps.** Each topic file has a "Gaps" section. Notable ones:
  - no European statement on a coach's scope of practice was found, so the knowledge base uses an Australian register;
  - the cardiac red flags rest on AHA and NHS sources because the ESC 2020 guideline had no quotable abstract;
  - several hypertrophy volume thresholds come from a preprint and are labelled as such.
- **Patient information:** NHS pages and the ACOG FAQ are patient information, rated as expert opinion.
- **Testing:** single-turn scenarios only. Multi-turn coaching (intake, then plan, then check-ins) is not yet covered by automated tests.
- **AI errors:** the coach can still make mistakes. A qualified professional should review plans for people with health conditions.

## Licence

- **Code** (the Python scripts in `research/tools/`, `tools/`, `tests/` and `.claude/skills/evidence-coach/scripts/`): MIT, see [`LICENSE`](LICENSE).
- **Text written for this project** (the agent and skill files, reference files, topic files, research notes, claim texts, tests and the README files): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Not covered by either licence:**
  - The verbatim quotes in `research/claims/*.jsonl` (the `quote` field) remain under their publishers' copyright. They are included as short, attributed quotations so that each claim can be checked against its source.
  - The cited works themselves, listed in `SOURCES.md`, are not included.
