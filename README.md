# Evidence Coach

An evidence-based training coach skill for AI coding agents. It helps athletes directly, or assists personal trainers with plans and client analysis. It covers strength and hypertrophy, running (including trail and ultra), cycling, climbing, and general fitness and mobility.

Every number it uses comes from a knowledge base of 613 claims from 267 sources. A script checked each claim's quote and numbers against the saved source text.

> **Not medical advice.** The coach screens for red flags and refers people to clinicians; it does not diagnose or treat. In an emergency, call 112 (EU), 999 (UK) or your local emergency number.

## Install

Requires Node.js 22.20 or later:

```bash
npx skills add 0x2668/evidence-coach --skill evidence-coach
```

The CLI lets you choose your agents, or name them with `-a`:

| Tool | `-a` |
|---|---|
| Claude Code | `claude-code` |
| ChatGPT (Codex CLI) | `codex` |
| Gemini CLI | `gemini-cli` |
| Antigravity | `antigravity` |
| Grok Build | `grok` |
| Cursor | `cursor` |

Add `-g` to install for all projects. Activity file analysis also needs Python 3.

Gemini Code Assist has no entry in the CLI. Its agent mode runs on Gemini CLI, but its docs do not confirm skill support, so open a clone of this repository there: it reads `GEMINI.md`.

## Use

Ask your agent about training, or invoke the skill by name if your tool supports it:

```
I want to run my first 50 km trail race in 16 weeks. Build me a plan.
```

## What it does

- **Checks red flags first:** chest pain during exercise gets an emergency instruction, not a cool-down.
- **Stays in scope:** no diagnosis, treatment, restrictive diets or medication advice, and no dosing for steroids or SARMs.
- **Builds plans:** tables with sets and reps or time and zone, RPE/RIR, progression and check-ins.
- **Shows the evidence:** contested areas are labelled, and where the evidence gives no figure, the coach says so.
- **Reads training data:** GPX, TCX, CSV and FIT files; Strava and Google Calendar if connected; Garmin Connect through scripts in a clone ([setup](tools/garmin/README.md)).
- **Protects health data:** it stores nothing without explicit consent.

## Limitations

- Automated tests ran only in Claude Code, and only on single messages. The other tools are supported through the skills CLI but untested. See [`tests/results.md`](tests/results.md).
- Many studies are in young, trained men, and some areas have evidence gaps, listed in the [reference files](skills/evidence-coach/references/).
- The coach can make mistakes. A qualified professional should review plans for people with health conditions.

## Evidence and new sports

- [`SOURCES.md`](SOURCES.md) lists every source. [`research/PROTOCOL.md`](research/PROTOCOL.md) describes the method, and [`research/README.md`](research/README.md) how the knowledge base was built. Source texts are not included, because they belong to their publishers.
- To add a sport, clone this repository and ask the agent to `add sport swimming`. It researches and verifies the evidence, then adds a reference file.

## Licence

Code is [MIT](LICENSE). Project text is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Quotes in `research/claims/` remain under their publishers' copyright.
