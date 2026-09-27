# ADR 0003 — Repository work is the only evidence; tutorials are removed

- **Status**: Accepted — absorbs the superseded *Grounded on-demand tutorials*, *Interactive sandbox tutorials*, *Completion via a local daemon with three gates*, and *Two credentials per session* (formerly 0003–0006)
- **Date**: 2026-09-27
- **Deciders**: Go Frendi
- **Context tags**: evidence, tutorials, scope, simplicity

## Context

Grit had two evidence sources: a task in the user's repository, verified by git and the hook log, and an interactive tutorial — a ~20 KB HTML page the assistant authored per concept, whose check ran in a browser sandbox and whose completion reached the ledger through a daemon, three gates and two credentials.

Measured, not argued:

- **The tutorial path never produced a score.** The one machine with real usage had 840 recorded assistant edits and 0 tutorials, 0 ledger rows; its 3 evidence rows were recorded by hand.
- **A simulated session could not complete one as instructed.** The judge credential existed only on the daemon's stderr — `daemon.log` when detached, mentioned nowhere — one per page load, labelled only by concept, so after a reload the assistant judged a session with no justification in it. Gate 1 was the page's own report, recorded as `verified-by-execution` although nothing was executed. Each was fixable; together they showed that the most machinery in the product guarded the path nobody used.
- **Its ceiling was already `practised`.** A sandbox pass weighed 0.2 against 0.5 and could never reach `shipped`: the design itself held that an exercise does not show you can do it in your own stack.

## Decision

> A task in a repository, done by the user, with a check that passes and a verdict from `verify_edit.py`, is the only evidence. There are no tutorials, no sandbox source, no ledger, no gates and no session credentials.

"Teach me X" still creates a task, not a lesson — now a task in a small practice repository the assistant scaffolds, with the real toolchain and a failing test, scored like any other repository work.

## Rationale

- **One verified path beats two half-verified ones.** The repository path has an execution the tool can see (git), an author the hook can see, and a check the user runs in their own toolchain. The tutorial path had a check the daemon could not see and a verdict delivered by hand.
- **The removed machinery defended only itself.** The ledger, the three gates, the report and judge tokens, `sessions.json`, the page template and its Worker existed to make tutorials trustworthy. None of it touched repository work.
- **The pedagogy survives without the page.** Retrieval practice with feedback ([Rowland 2014](https://doi.org/10.1037/a0037559), g = 0.50) is what a repository task with a failing test already is. The "guided" option — walk me through it, you still write it — is the adaptive, on-a-measured-gap guidance [ADR 0002](0002-withhold-guidance-by-default.md) calls for, without a second artifact.

## Alternatives Considered

- **Ground every tutorial in a task with a check** (formerly 0003) — superseded. It held that "teach me X" creates a task, not a lesson, and that no lesson library is built: tutorials untethered from a check produce no domain learning (Roll, Aleven, McLaren & Koedinger: help-seeking improved, domain learning did not — "help helps, but only so much"), and transfer is weak across the whole family ([St. Hilaire, Chan & Ahn 2024](https://doi.org/10.3758/s13423-023-02359-2): g = 0.54 tested, g = 0.04 transfer; [Kulik et al. 1990](https://doi.org/10.3102/00346543060002265): d ≈ 0.5 on teacher-made tests, ≈ 0.08 standardised). **What survives:** all of it except the tutorial — a request to learn still becomes a task with a check, now in a repository.
- **Interactive sandbox tutorials, with a declared evidence gap** (formerly 0004) — superseded. A JavaScript sandbox rendered in the dashboard, the user writing code against an executable check, declared a weaker oracle than the repository. It was also the most guidance-dense artifact in the design, and so the one where any routing error turns into expertise-reversal harm. **What survives:** the rule that a check outside the user's own stack is weaker, which is why the only remaining check is the repository's.
- **Completion reported by a local daemon, with three gates** (formerly 0005) — superseded. A page cannot write files and a `file://` origin cannot `fetch()` loopback, so the daemon owned the session and ledger, and a concept was earned only on check + submitted justification + the assistant's judgment. Rejected within it and still rejected: a clipboard handoff (depends on the user remembering), trusting "done" (self-report), two gates (completion becomes a fact about typing). **What survives:** the daemon, as a read-only dashboard server whose only write is preferences; and check-then-justify, now in conversation — the assistant records a task only when the check passed and the justification was sound.
- **Two credentials per session: the page reports, the assistant judges** (formerly 0006) — superseded. One shared token let the page award itself gate 3 with a single `fetch()`; the fix split a report token (page) from a judge token (assistant), derived `earned` in one function, kept raw tokens out of the readable ledger, persisted sessions at `0600`, and made the first verdict stand. **What survives:** CORS stays closed, because loopback is not a boundary on a developer's machine — any `npm run dev` could otherwise read every project you work in; a level is still derived in one function and stored nowhere; the remedy for a wrong record is still a new measurement, never an edit, which is now the rule for `evidence.jsonl`, `tasks.jsonl` and `authorship.jsonl`; and the lesson that a guarantee written in a docstring is a claim, not a measurement.
- **Fix the tutorial path and keep it** — rejected. `--pending`, session reuse and an honest gate-1 label were built and worked in simulation. They made a path nobody used correct, and left a check the daemon could never see.

## Consequences

- **Beginners are served through a practice repository.** Two distinct unaided tasks there reach `shipped`, although the test was written by the assistant. That is a deliberate, unvalidated consequence ([DESIGN.md §4](../DESIGN.md), item 6).
- **Legacy evidence stays and scores nothing.** Rows with `"source": "sandbox"` remain in the append-only file; `score_concept` skips any source it does not credit.
- **`assistance: partial` now means one thing** — the user chose *guided*.
- **The justification is judged in conversation and not recorded as its own gate.** Its only trace is whether the task was recorded, and as `--failed` or not. The judgment is as unvalidated as it was ([DESIGN.md §4](../DESIGN.md), item 4).
- **Much less to break.** `serve.py` went from 1,528 lines to about 800; the tutorial template, the ledger, sessions and eleven daemon properties that tested them are gone with the code they covered.
- **Numbers 0004–0006 are not reused.** Their decisions live above; git keeps the originals.

## Backlinks

- [ADR index](README.md)
- [ADR 0002 — Withhold guidance by default](0002-withhold-guidance-by-default.md)
- [ADR 0009 — A graded score, derived from capped evidence](0009-graded-score-from-capped-evidence.md)
