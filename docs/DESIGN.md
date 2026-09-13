# Design

The shape of Grit: the workflow, the on-disk layout, the data contracts. For *why* the design is this way, and what was rejected, see [`adr/`](adr/index.md).

**Status:** design, not implementation. No component described here is built.

---

## 1. The workflow

Every time the AI is about to work, the user is asked. There is no mode to select and no bypass affordance to decline — that is a structural fix to the failure mode the original design had, not a prompt-level one.

```
You: add rate limiting to the login route

AI:  This needs: token bucket algorithm, atomic counters, middleware ordering.
     Do you want to do this yourself?          (default: yes)

     [ Do it myself ]  [ You do it ]

── if "do it myself" ──────────────────────────────────────────────

AI:  Checking your profile for these three concepts...
     token bucket        — profiled: weak       → tutorial offered
     atomic counters     — profiled: strong     → handed over
     middleware ordering — NOT PROFILED         → one probe question

AI:  [probe on unprofiled concepts only]
     "If two requests arrive in the same millisecond, what should happen
      to the counter?"

── routed by the ANSWER, not the claim ────────────────────────────

     answered well  → no tutorial, hand over the task
     answered badly → offer generated interactive tutorial
     unsure         → offer tutorial

── you work, unassisted, with the AI answering questions ──────────

AI:  Run the check:  npm test -- rate-limiter

── on pass ───────────────────────────────────────────────────────

AI:  Green. Justify it: why does this hold under concurrent load?
     What stops the race?

     answered well  → close. concept logged as yours. profile updated.
     answered badly → concept logged as assisted; drill offered.
```

Three properties carry the design — see the ADRs for the evidence behind each:

- **The trigger is a moment, not a mode** ([ADR 0001](adr/0001-route-on-measured-proficiency.md)).
- **Routing is on demonstration, never on declaration** (ADR 0001).
- **Feedback is socratic and comes after the check** ([ADR 0003](adr/0003-withhold-guidance-by-default.md)).

---

## 2. Principles

### What may be delegated to the user, and what may not

"Ask the user when unsure" is right for *configuration* and wrong for *measurement*. Stated explicitly, because otherwise it silently licenses asking the one question the battery exists to avoid.

| Uncertainty about… | Ask the user? | Why |
|---|---|---|
| Tutorial format, depth, pace | **Yes** | Cheap to get wrong; costs annoyance only |
| Stack, repos, workflow, notification style | **Yes** | Factual — the user knows their setup |
| Whether they know a concept | **No** | The one case where asking is *systematically* wrong |
| Whether the battery predicts real work | **No** | Empirical — nobody can answer it, including the user |
| Whether a tutorial format works for them | **Partly** | Ask, then check against outcomes; the check overrules |

**The rule:** the user may configure the product. The user may not certify their own proficiency, and may not adjudicate whether the instrument is valid.

### Preference is a prior, corrected by outcomes

Preferences are cheap to collect and easy to state wrong. People choose "just give me the answer" and are then unhappy they learned nothing — the exact failure this product exists to address.

So preference sets the **default**, and outcomes get to **overrule** it. A user who chooses "worked example" every time, whose justifications keep failing, is receiving a format that is not working. The system says so rather than honoring the preference silently. The correction is surfaced, never applied by stealth.

**A preference that turns the mechanism off should be visible, not silent.** "Default: just do it for me" is the user's call, but it is recorded and shown, because a configuration that quietly disables the product's only function is the METR pattern — feeling fine while capability erodes, with nothing on screen to contradict it.

### The honest claim

This design **may avoid harm**. It does not claim to make anyone more skilled. Bastani et al.'s guardrailed arm was statistically indistinguishable from control; no study shows a tool producing skill *gains* over working unaided. The achievable outcome is *less erosion*.

---

## 3. What v1 does

- **Graded scoring from repository work** — the primary evidence source ([ADR 0014](adr/0014-graded-score-from-capped-evidence.md)) *(built)*
- ~~**Onboarding battery**~~ — deferred. ADR 0014 removed the need for a battery to exist before anything can be scored; real tasks populate the profile directly ([ADR 0006](adr/0006-calibrated-battery-not-mini-games.md))
- **Preferences questionnaire** — format, depth, pace; editable, prior overridable by outcomes
- ~~**The router**~~ — deferred with the battery. Concepts are named by the assistant and confirmed by the user per task ([ADR 0001](adr/0001-route-on-measured-proficiency.md) still governs how routing must work *if* it is built)
- **Gap-triggered tutorial generation**, scoped to your repo and cached per concept ([ADR 0005](adr/0005-grounded-on-demand-tutorials.md))
- **Interactive tutorial runtime** — self-contained HTML sandboxes where you write code and a check runs in a worker ([ADR 0008](adr/0008-interactive-sandbox-tutorials.md))
- **The local daemon** (`grit serve`, loopback only) — owns the session and the ledger, and is the only writer of completion records ([ADR 0009](adr/0009-completion-via-local-daemon.md))
- **The derived profile** — `~/.grit/profile.json`, folded from the ledger on every write. A tutorial pass caps at `recall`; only real work asserts `strong` ([ADR 0010](adr/0010-profile-derived-from-ledger.md))
- **Acceptance checks** — command/test; a task closes on a pass, not on your say-so
- **Socratic justification after the check** — where a concept is claimed or not
- **Dashboard** — the entry gate: battery, profile, decay, history ([ADR 0004](adr/0004-measure-the-effect.md))

**Not in v1:** team or hosted features, non-coding domains, cross-user benchmarking, a tutorial library (gap-triggered only), and any claim beyond harm avoidance.

---

## 4. On disk

Two locations, deliberately separated:

- **`~/.grit/`** — **you**. Proficiency, history, tutorials, dashboard. Learning is a property of the person, not the repo.
- **`./.grit/`** — **this work**. The plan, the tasks, their checks. Acceptance checks must run in this repo against this code.

```
~/.grit/
├── ledger.json           # ground truth: what happened (ADR 0009)
├── profile.json          # DERIVED from the ledger — never edit by hand (ADR 0010)
├── preferences.json      # format, depth, pace — askable, overridable
├── sessions/             # what happened, by date
├── tutorials/            # generated, cached, reusable across projects
│   └── <name>.html.meta.json   # {"concept": "...", "via": "battery|probe|work"}
└── dashboard/            # hot-reloaded web view

./.grit/
├── tasks.json            # what is being done here
├── checks/               # acceptance checks for those tasks
└── missions/             # per-task state
```

---

## 5. Data contracts

### Profile — `~/.grit/profile.json`

**Derived, not authoritative** ([ADR 0010](adr/0010-profile-derived-from-ledger.md)). The daemon folds `ledger.json` into this on every write. Edit the ledger, not this file. Actual shape:

```json
{
  "version": 1,
  "derived_from": "ledger.json",
  "concepts": {
    "token-bucket": {
      "proficiency": "recall",          // weak | recall | strong
      "confidence": 0.6,
      "source": "tutorial",             // work | probe | battery | tutorial
      "measured_at": "2026-09-13T10:00:00+00:00",
      "last_evidence": "2026-09-13T10:05:00+00:00",
      "decay_after_days": 90,
      "age_days": 12,
      "stale": false,
      "evidence": { "earned": 2, "unearned": 0, "routing_via": ["battery"] }
    }
  }
}
```

Three rules carry meaning:

- **A tutorial pass caps at `recall`.** `strong` is reachable only from `source: work`. This is [ADR 0008](adr/0008-interactive-sandbox-tutorials.md)'s weaker-oracle warning enforced in the data model, not merely stated.
- **A tutorial that fires and fails is a negative signal**, not a neutral one — it only fired because a gap was measured, and the gap did not close. It records `unearned` and does not upgrade.
- **Decay flags, it does not downgrade.** Past `decay_after_days` the entry is marked `stale` and confidence is halved; the level is left alone. Lowering the level would assert a change nobody measured. The router decides what staleness means.

`evidence.routing_via` is what makes the [ADR 0007](adr/0007-critical-path-battery-validity.md) audit possible: without it there is no way to tell whether the *battery* is the thing mis-routing.

`source` records where the value came from — `battery`, `probe`, or `work`. Real work is ground truth and outranks a battery result; this field is what lets the router prefer it.

### Preferences — `~/.grit/preferences.json`

Not yet implemented ([ADR 0010](adr/0010-profile-derived-from-ledger.md) governs the profile only). Target shape:

```json
{
  "version": 1,
  "format": "socratic",
  "depth": "standard",
  "pace": "one-at-a-time",
  "default_do_it_myself": true,
  "visible_overrides": []
}
```

`default_do_it_myself: false` is permitted and shown on the dashboard. `visible_overrides` records places where outcomes have contradicted a stated preference.

### Task — `./.grit/tasks.json`

```json
{
  "version": 1,
  "id": "001",
  "title": "Add rate limiting to the login route",
  "requires": ["token-bucket", "atomic-counters", "middleware-ordering"],
  "acceptance": {
    "type": "command",
    "run": "npm test -- rate-limiter",
    "expect_exit_code": 0
  },
  "justification": "Why does this hold under concurrent load?",
  "status": "pending",
  "routing": {
    "token-bucket": {
      "decision": "tutorial",
      "via": "profile",
      "check": "sandbox",
      "tutorial": "~/.grit/tutorials/token-bucket.html"
    },
    "middleware-ordering": { "decision": "handover", "via": "probe" }
  }
}
```

`routing.via` records whether the decision came from the profile or a probe. Without it, the router's accuracy cannot be audited — and auditing it is the critical path ([ADR 0007](adr/0007-critical-path-battery-validity.md)).

`routing.check` records *which kind* of check closed the concept — `sandbox` or repository. A concept taught by an interactive tutorial and verified in the sandbox is **not** verified in the repository, and the ledger must not collapse the two ([ADR 0008](adr/0008-interactive-sandbox-tutorials.md)).

### Acceptance check types

| Type | Meaning | Example |
|------|---------|---------|
| `command` | Run a shell command, check exit code | `npm test` → 0 |
| `test` | Named test(s) must pass | `pytest tests/test_rate.py` |
| `artifact` | A file must exist and match a shape | `openapi.yaml` has a `429` response |
| `sandbox` | Interactive tutorial check, in JavaScript | token-bucket exercise passes |
| ~~`manual`~~ | **Not implemented, and deliberately so** — see below | — |

**Two strengths of check, and they are not interchangeable.** A `command`, `test`, or `artifact` check verifies the user's real work in their real repository. A `sandbox` check verifies the concept in a JavaScript exercise (ADR 0008). **Passing a sandbox check does not mean the repository is fixed**, and every result carries which kind closed it so the ledger cannot present them as equivalent.

**`manual` is removed rather than unimplemented.** It was listed as "the escape hatch for genuinely subjective work". It is the hole through which `earned` becomes meaningless: a check nobody can fail is the user certifying their own proficiency, which ADR 0001 exists to eliminate. The daemon hardcodes `check_type: "sandbox"` and has no path to record any other kind, so the code has always been stricter than this table. The table was wrong.

Consequence: **work with no executable check cannot be recorded at all.** Non-coding domains are out of scope not because they are uninteresting but because there is no oracle, and without one this product has nothing to offer that an ordinary assistant does not.

`command` and `test` are preferred — they cannot be faked by optimism, and [ADR 0004](adr/0004-measure-the-effect.md) requires measurement rather than assertion. `manual` is the escape hatch for genuinely subjective work, and is marked as such.

### Ungrounded work

When no acceptance check is possible — non-coding tasks — the schema still applies but `acceptance.type` is `manual`, and **the socratic justification cannot be scored against ground truth.** The guarantees are weaker here. This is documented rather than implied, because the coding guarantees do not transfer.

---

## 6. Build order

Sequenced by dependency, and by what would be wasted if the critical path fails.

1. **The battery and the profile** — nothing routes without these
2. ~~**The router**~~ — deferred. Scoring from real tasks (ADR 0014) does not need it
3. **The tutorial generator + runtime** — gap-triggered, grounded, cached per concept
4. **The check + justification loop** — where a concept is claimed or not
5. **The dashboard proper** — history, decay, trends, achievement

The **tutorial runtime** ([`skills/grit/tutorial.template.html`](../skills/grit/tutorial.template.html)) is a working, tested artifact and can be built against now. It is self-contained, runs offline (Design §8), enforces a self-test before accepting any submission, and distinguishes a sandbox pass from a repository pass.

The **daemon** ([`skills/grit/serve.py`](../skills/grit/serve.py)) is also working and tested. It is the skill's companion file — discovered automatically because it sits in the skill's directory. It owns the tutorial session and the ledger, and is the only writer of completion records — the page reports over loopback and never touches the ledger itself ([ADR 0009](adr/0009-completion-via-local-daemon.md)):

```sh
python3 skills/grit/serve.py --root ~/.grit     # --port N | --port 0 | GRIT_PORT
```

It prints its URL and writes the same address to `~/.grit/daemon.json`, so nothing downstream has to assume a port. Open that URL for the dashboard; launch a tutorial at `<url>/tutorial/<name>.html` and the daemon injects a session token as it serves it.

**Tutorials live in `~/.grit/tutorials/` and the directory starts empty.** The daemon does not ship a concept library — that is a deliberate consequence of ADR 0005 (no lesson library; tutorials are generated per gap).

It also means **the directory has no way to become non-empty**, because nothing generates a tutorial yet. That is the open end of the whole design: the profile is derived from the ledger, the ledger is written by tutorial sessions, and tutorial sessions need a file nobody produces. Until the generator exists there is no end-to-end loop, only the pieces of one.

The template can be copied in by hand to exercise the runtime, but it is a fixture, not a lesson — its check is hardcoded to fail. See [dev-fixtures.md](dev-fixtures.md); keep it out of user-facing instructions.

The dashboard appears in 1 and 5 because the battery is inherently interactive and the profile is inherently visual. **It is the entry gate, not a status page built last** — an earlier build order had it at the end and that was wrong ([ADR 0004](adr/0004-measure-the-effect.md)).

**Templates ship with each artifact**, because a generated dashboard with no history is a blank screen and an adaptive battery needs an item bank before it can measure anything. But **"checked in" is not "validated"**: a battery in version control is *reproducible*, not *accurate*, and every routing decision inherits its errors invisibly.

---

## 7. What is still unproven

Stated here rather than left to be discovered.

1. **Battery validity.** Does it predict real-work proficiency? If not, routing runs on noise and the design collapses. This is the critical path ([ADR 0007](adr/0007-critical-path-battery-validity.md)).
2. **Bias against experts.** The battery may under-rate concepts used daily but rarely quizzed.
3. **The probe is guidance.** One question per unprofiled concept is external guidance, asked of an expert. Whether one question falls under the harm threshold is untested ([ADR 0003](adr/0003-withhold-guidance-by-default.md)).
4. **Retention is unmeasured.** Only behaviour and routing are observable. No design here measures what you can do in a month.
5. **Template staleness.** A concept taxonomy is a claim about a field, and fields move. An unmaintained template gets vaguer and mis-routes silently.
6. **Sandbox tutorials do not transfer by default.** A user can pass a JavaScript rate-limiter exercise and still fail to implement one in their Go service. The transfer question is not in the current study and should be added to Q1 ([ADR 0008](adr/0008-interactive-sandbox-tutorials.md)).
7. **The judgment gate is unvalidated.** A concept counts as earned only when the assistant judges the justification sound (ADR 0009), and there is no ground truth for that judgment. It is measurable — judge-sound answers that later fail on the same concept falsify it — but it has not been measured, and it is load-bearing.
8. **Population transfer.** The mechanism evidence is from novices. The one study in the target population (METR, 16 experienced developers) measured speed, not skill.

---

## 8. Environment

Non-negotiable for the measurement layer ([ADR 0004](adr/0004-measure-the-effect.md)):

- **Inference local.** Concepts do not leave the machine. `battery`, `profile`, and `tutorials` are inference-heavy and run against a local model by default.
- **Measurement local.** `dashboard`, `sessions/`, and `profile.json` are pure localhost.
- **Only `tutorial generation` may reach a remote model**, and only with explicit per-session consent — it is the one operation that needs capability a local model may not have.

This is a hard boundary, not a preference: a tool that profiles your weaknesses is a liability if that profile is transmitted.
