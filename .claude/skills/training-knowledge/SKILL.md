---
name: training-knowledge
description: Evidence-based knowledge base for coaching strength, hypertrophy, running (including trail and ultra), cycling, climbing, general fitness and mobility, with safety screening, special populations, load monitoring, recovery, sports nutrition within a coach's scope and behaviour change. Every rule cites verified claims with source, year and evidence level. Use when planning or adapting training, checking red flags, or answering training and nutrition questions.
user-invocable: false
---

# Training knowledge base

Rules here and in `references/` were built only from claims whose quotes and numbers were verified against the saved source text (research log: `research/notes.md`). IDs in brackets, such as [STR-05], point to the evidence table at the end of each reference file (source, year, evidence level, population, link). `SOURCES.md` in the project root lists every source.

## How to use this knowledge base

1. Check red flags first (`references/safety-screening.md`, or the summary in your instructions).
2. Read the reference file for the discipline or question before giving numbers you are not sure of.
3. Use the population column of the evidence table: many studies are in young, trained men; say so when you apply them to someone else.
4. Present anything listed under "Contested areas" as contested: give the practical default and say experts disagree.
5. If no rule covers the question, say the evidence does not give a figure and choose conservatively, labelled as judgement.

<!-- reference table: generated from research/topics.json -->
| Read this file | When |
|---|---|
| `references/safety-screening.md` | Screening (PAR-Q+, ACSM), red flags, pain during training, heat illness, hyponatremia, rhabdomyolysis, concussion, overtraining, REDs warning signs, scope of practice, steroids and SARMs, GDPR |
| `references/special-populations.md` | Health dose (WHO), starting from sedentary, older adults, pregnancy and postpartum, adolescents, chronic conditions (diabetes, hypertension, heart disease, osteoarthritis, back pain, osteoporosis) |
| `references/strength.md` | Volume, load, RIR/RPE, rest, progression, deloads, periodization, autoregulation, concurrent training, bodyweight training, mobility and warm-up, knee pain programming |
| `references/endurance.md` | Zones (HR, pace, power, talk test), HRmax, critical speed and FTP, intensity distribution, beginners, running volume and injury, trail and ultra, taper, strength for endurance |
| `references/climbing.md` | Hangboard and finger training, campus board, youth growth plates, finger and shoulder injuries, warm-up, low energy availability in climbers |
| `references/monitoring-recovery.md` | sRPE, monotony and strain, ACWR (contested), HRV, check-ins, wearable data validity, recovery methods, sleep, injury prevention, return after illness |
| `references/nutrition.md` | Protein, carbohydrate, fuelling and fluids for long events and ultras, hydration, weight loss and crash-diet requests, supplements and contamination, adolescents, when to refer to a dietitian |
| `references/behaviour-change.md` | Intake and goal setting, motivation, habits, adherence and dropout, check-in conversation, declining unsafe requests, weight and appearance language, limits of AI coaching |
<!-- end of reference table -->

## Evidence levels

- `consensus`: position stand, consensus statement or guideline of a professional or official body.
- `meta-analysis`: systematic review with or without meta-analysis.
- `single study`: one trial or cohort; apply cautiously.
- `expert opinion`: narrative review, Delphi, textbook, official patient information; `(practitioner)` marks coaching sources used only as a supplement.

## Defaults at a glance

### General health dose (adults)
- 150-300 min/week of moderate or 75-150 min/week of vigorous aerobic activity, plus muscle-strengthening on 2 or more days per week [POP-01, POP-02]. These are minimums for health, not a ceiling [POP-12].
- Starting from sedentary, after a clear PAR-Q+: 20-60 min of low-to-moderate exercise on 3-5 days/week mixing aerobic and strength work, building toward 150 min/week or more [POP-65].
- Older adults: multicomponent balance and strength training on 3 or more days per week [POP-08]. Children and adolescents: an average of at least 60 min/day [POP-09].

### Strength and hypertrophy
- At least 2 sessions per week for all major muscle groups [STR-01]. Strength: loads of at least 80% 1RM, 2-3 sets, full range of motion [STR-03]. Hypertrophy: at least 10 weekly sets per muscle is a standard target; about 4 is a minimum effective dose (preprint figure) [STR-02, STR-19].
- Effort: about 2-3 reps in reserve; failure is not required [STR-05]. RIR-based RPE: RPE 8 = 2 RIR [STR-29]. People misjudge RIR by about 1 rep [STR-32].
- Progression: double progression [STR-35]; load steps of 2-10% once 1-2 reps above target [STR-13].
- Deload: cut sets, reps or effort rather than stopping; strength athletes typically deload about 6 days every 5-6 weeks [STR-37, STR-38, STR-39].

### Endurance
- 3-zone model as the reference; say which scheme a zone number belongs to [END-02, END-03]. Without tests use the talk test and RPE [END-14].
- HRmax estimate 208 - 0.7 x age only when no measured value exists [END-15].
- Mostly easy training; pyramidal distribution for recreational athletes [END-01, END-07, END-08].
- Runners: keep each run within 10% of the longest run in the previous 30 days; the weekly "10% rule" is not protective [END-34, END-30].
- Taper about 2 weeks, cutting volume by about 41-60% and keeping intensity and frequency [END-50].
- Endurance athletes: add two to three strength sessions per week, including heavy loads [END-53].

### Climbing
- Hangboard about 2 days per week with 48-72 h between sessions (practitioner dosing) [CLB-26]. No feet-off or dynamic campus boarding under 18 [CLB-34]; reduce finger training intensity during the growth spurt [CLB-37].

### Monitoring and recovery
- Check-ins rated against the athlete's normal; short daily, longer weekly [MON-19, MON-20, MON-21].
- Flag single-session spikes; do not use ACWR thresholds to predict injury [MON-07, MON-08, MON-11].
- Strength training is the most effective exercise-based injury prevention (RR 0.32) [MON-39].
- After a respiratory illness: no training with symptoms at rest, then an easy 10-20 min test session at 60-70% of normal intensity [MON-45, MON-46].

### Nutrition (within scope)
- Protein 1.4-2.0 g/kg/day for adults who train; about 1.6 g/kg/day for hypertrophy [NUT-01, NUT-03].
- Carbohydrate 30-60 g/h in events longer than 60 minutes; up to 90 g/h only in long events and after gut training [NUT-13, NUT-23].
- Keep body-mass loss during exercise below 2%; drinking to thirst is a safe default for recreational athletes [NUT-24, NUT-31].
- Weight loss: at most 0.5-1.0% of body weight per week; crash diets are declined and referred [NUT-41, NUT-49].
- Adolescents: food first, no performance supplements [NUT-61, NUT-63].

### Behaviour
- Set goals together and pair them with self-monitoring and feedback [BEH-58]; beginners get process or learning goals, plus a fallback minimum session [BEH-28].
- Sedentary beginners: start with short, easy sessions as a low-risk default; whether session length drives dropout is contested [BEH-42, BEH-62].

## Contested areas (details in the reference files)

- Strength: upper useful volume limit, training close to failure, rest periods for trained lifters, periodization models, deload timing, interference from endurance training (`strength.md`).
- Endurance: polarized versus pyramidal distribution, the weekly ten-percent rule, FTP as a threshold, naming of the moderate zone (`endurance.md`).
- Climbing: best hangboard protocol, youth age limits for campus and hangboard training, antagonist training (`climbing.md`).
- Monitoring: ACWR, value of HRV-guided training (`monitoring-recovery.md`).
- Nutrition: per-meal protein ceiling, carbohydrate per hour in ultras, drinking to thirst versus a plan, energy-availability thresholds, ketogenic diets, creatine in adolescents (`nutrition.md`).
- Safety: training through pain (pain-free versus pain-monitored), whether REDs is a diagnosable syndrome (`safety-screening.md`).
- Behaviour: SMART versus open goals, session length and adherence (`behaviour-change.md`).

## Activity files

Summarise a GPX, TCX, CSV or FIT file (duration, distance, elevation, heart rate, power, optional time in HR zones and per-km splits):

```
python3 .claude/skills/training-knowledge/scripts/activity_summary.py <file> [--zones 130,150,165] [--splits]
```

`--zones` takes the upper heart-rate limit of each zone except the last. FIT support covers standard record and session messages; if a FIT file fails, ask for a GPX or TCX export or use Strava.
