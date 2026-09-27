# Architecture

How grit actually works, end to end — **the mechanism**.

For the principles that constrain it and the limits it has not escaped, see [DESIGN.md](DESIGN.md). For individual decisions and what was rejected, see [`adr/`](adr/README.md).

---

## The one-sentence version

A hook watches who writes code, git says what changed, and a local daemon turns those two facts plus your own justification into a per-concept level you did not award yourself.

## Three processes, and they barely know each other

| Process | Lives for | Writes | Never does |
|---|---|---|---|
| **the hook** (`hooks/grit-hook.py`) | milliseconds, once per tool call | `~/.grit/projects/<key>/authorship.jsonl` | talk to the daemon, block an edit |
| **the assistant** (`skills/grit/SKILL.md`) | your session | evidence, via `score.py` | decide the check passed |
| **the daemon** (`skills/grit/serve.py`) | until stopped | `~/.grit/*` | run your acceptance check |

They are deliberately not coupled. The hook cannot depend on the daemon running, or every file edit would inherit the daemon's uptime. The daemon cannot depend on the hook, or a fresh machine could not render a dashboard. They meet through files.

## The files, and which one is the truth

Everything is JSON or JSONL on disk. There is no database and no server you do not control.

```
~/.grit/                             everything lives here — nothing in the project
  evidence.jsonl      append-only    THE SOURCE OF TRUTH for your score
  ledger.json         replace        tutorial sessions and their three gates
  sessions.json       replace, 0600  live tokens; survives a daemon restart
  preferences.json    replace        theme, callsign, tutorial depth/format, default choice — configuration only
  projects.json       replace        which project paths have an authorship log
  daemon.json         replace        where the daemon is listening right now
  tutorials/          files          hand-authored tutorial pages

  projects/<key>/                    per project — raw observation, keyed by a
                                      hash of the project's real path
    authorship.jsonl  append-only    every byte the assistant wrote, here, plus offered/applied events
    tasks.jsonl       append-only    each verify_edit verdict, with git's line counts
    snapshots/<task>.json            the git baseline for one handover
    off               marker         killswitch for this project

  asked/              markers        one file per session already prompted
  .last-event         replace        the hook's de-dup window (DEDUPE_WINDOW)
  hook-errors.log     append-only    the hook never raises; it logs and exits 0
  daemon.log          append-only    stdout/stderr when started with --daemon
```

Everything below `tutorials/` is scratch, not record: delete any of it and nothing about your score changes — including `projects/`, whose loss only means authorship history for those repos is gone, not your evidence or score.

**`evidence.jsonl` is the only file that matters.** The score is recomputed from it on every read and stored nowhere, so there is no cached number to go stale and nothing to edit into being true. Delete it and your score is genuinely gone; edit it and you have only lied to yourself.

The split is deliberate: **observations are keyed by project, proficiency is per person** — and both now live under `~/.grit/`, not inside the repository. Learning token buckets in one repository does not un-learn them in the next.

## The path a score takes

```mermaid
flowchart TD
    subgraph OBSERVE ["① Observation — automatic"]
        W["assistant calls Write / Edit"] -->|PreToolUse| H["grit-hook.py"]
        B["assistant calls Bash"] -->|PreToolUse| H
        H --> H1["append authorship.jsonl<br/>edits: exact lines · shell: files it wrote"]
        H --> H2["register project in ~/.grit/projects.json"]
    end

    subgraph WORK ["② A task you do yourself"]
        C["agree concepts, you confirm"] --> SNAP["verify_edit.py snapshot<br/>records the git baseline"]
        SNAP --> DIY["you write the code<br/>assistant answers, writes nothing"]
        DIY --> CHK["your acceptance check runs<br/>must actually pass"]
        CHK --> JUS["you justify the result"]
        JUS --> VER["verify_edit.py verify<br/>git diff + authorship log"]
    end

    subgraph SCORE ["③ Evidence → level"]
        VER -->|HUMAN-WRITTEN / ASSISTED / UNVERIFIED| EV["~/.grit/evidence.jsonl"]
        TUT["a completed tutorial<br/>(all three gates)"] --> EV
        EV --> CALC["score.py<br/>source × assistance × novelty"]
        CALC --> LV["learning → practised → shipped"]
    end

    subgraph VIEW ["④ Dashboard — polls, never pushed"]
        D["serve.py --daemon"] --> API["/score /authorship /tutorials /ledger"]
        API --> PAGE["browser, refreshes on focus + every 30s"]
    end

    H1 --> VER
    LV --> API
    H1 --> API

    style EV fill:#2d5a3d,color:#fff
    style LV fill:#2d5a3d,color:#fff
```

## The pieces

### `hooks/grit-hook.py` — the only un-arguable measurement

Runs as a `PreToolUse` and `PostToolUse` command hook. Before a tool call it appends an authorship row and asks once per session whether you would rather do it yourself; after a file edit actually ran it appends an `applied` row.

Three properties it must never lose, each of which was once broken:

- **It cannot block an edit.** Python exits `2` when it cannot open a script, and `2` is exactly the code both runtimes read as *block this tool call*. Every registration is therefore `python3 '<path>' || exit 0` — see [ADR 0007](adr/0007-hooks-must-fail-open.md).
- **Shell calls are observed, and opaque until they are.** An assistant editing through `python3 - <<EOF` produces no edit event. Before each shell call the hook fingerprints `git status` (every listed path's size and mtime) under `pending-shell/<tool_use_id>`; after it, a `shell-result` row names the files that changed. `verify_edit.py` treats a call that wrote nothing as harmless, one that wrote files as the assistant's, and one with no result as unobserved (`UNVERIFIED`). A commit is not a write — content is untouched. Its own in-flight call is excused only when the command is a plain `verify_edit.py verify` invocation. Without this, the assistant running the user's tests, or running `verify_edit.py`, voided every task the skill handed over. Limits: only paths `git status` lists are seen, so a write to an ignored file is invisible; an unignored build artifact counts as the assistant's.
- **One event, one row.** Two registrations can match one edit (user-level plus project-level, or zrb reading Claude's settings). A content hash inside `DEDUPE_WINDOW` de-duplicates; the window is narrow on purpose, because a wider one swallowed real retries.

The row that raises the once-per-session offer is still recorded — `PreToolUse` fires before the user answers, so the edit may be approved — but it carries `prompted: true`. The daemon's `taken` count is "offered, and no file edit happened in that session" — no unprompted edit, and no `applied` row confirming the prompted one was approved. Shell calls do not count against it, since in DIY mode the assistant still runs the user's tests. On an install without the `PostToolUse` registration it falls back to an inference, and an approved prompted edit with nothing after it reads as taken.

### `skills/grit/verify_edit.py` — who wrote it

Compares a git snapshot taken at handover against the tree now, and cross-references the authorship log.

| Verdict | Means | Scores as |
|---|---|---|
| `HUMAN-WRITTEN` | the tree changed, no assistant edits observed | `none` |
| `ASSISTED` | assistant edits landed in the window | `full` → zero credit |
| `NOTHING CHANGED` | the check passed without work | nothing recorded |
| `UNVERIFIED` | nobody was watching, or a shell ran unobserved | `full` |

The subtle one: **an absent authorship log is ambiguous.** No hook installed means nobody watched; a hook installed that recorded nothing means the assistant wrote nothing — which is the DIY case and *should* score. `doctor.is_watching()` distinguishes them. Conflating them made the first task in every fresh repository unscoreable.

### `skills/grit/score.py` — evidence → level

`credit = source_weight × assistance × novelty`, capped per task, summed, max 1.0. The constants and the reasoning behind each are [ADR 0009](adr/0009-graded-score-from-capped-evidence.md)'s; the user-facing table is in the [README](../../README.md#the-score).

`suggest_mode` is the router: `score.py level <concept>...` pre-selects *guided* only for a concept still at `learning` with a recorded failure, and *solo* otherwise, because guidance goes only where a gap was measured ([ADR 0002](adr/0002-withhold-guidance-by-default.md)).

A task's identity is `(source, project, task)` for repository work and `(source, task)` for tutorials — repository task ids are per-project sequences, so `001` in two repos is two tasks, while a tutorial is the same exercise wherever it runs. Full reasoning and the calibration errors that were caught by running it: [ADR 0009](adr/0009-graded-score-from-capped-evidence.md).

### `skills/grit/serve.py` — the daemon

Localhost only, no cross-origin. Three responsibilities: serve the dashboard and tutorials, own the three-gate ledger, and expose the score.

| Route | Returns |
|---|---|
| `/` | the dashboard (read from disk per request — no restart needed to edit it) |
| `/status` | everything `/grit` needs in one call, including the derived `notices` — a setting that switches the mechanism off is shown, never stored |
| `/score`, `/profile` | per-concept levels |
| `/authorship` | assistant-written lines per project |
| `/tasks` | each handed-over task's latest verdict, with git's line counts, totals per verdict, and the last 8 weeks of verdicts |
| `/tutorials`, `/ledger`, `/preferences`, `/themes`, `/health` | as named |
| `POST /tutorial/<report-token>/{check,justification}` | gates 1 and 2 — the justification carries the user's `prediction` alongside their `answer`, so gate 3 judges both |
| `POST /judgment/<judge-token>` | gate 3 |

**Gate 3, in practice.** `serve.py --root ~/.grit --pending` lists every justification awaiting a verdict — prediction, answer, and the code the page reported with gate 1 — each with the judge command for that session. Gate 1's row is labelled `reported-by-page`: the check ran in the browser, and this process executed nothing. Reloading a tutorial reuses a session nothing has been reported to, instead of minting another.

**Two credentials per session.** The page gets a *report* token and can only report gates 1 and 2. The *judge* token is printed to the daemon's terminal and never reaches the browser; `POST /tutorial/<report>/judgment` returns `403` on purpose. Without the split the page could award itself a pass with one `fetch()` — [ADR 0006](adr/0006-two-credentials-per-session.md).

**Gate 3 appends.** The first verdict stands; later calls return `409` with the standing verdict and the full history, and change nothing. A verdict you can overwrite is not evidence.

Editing `serve.py` needs a daemon restart. Editing `dashboard.html` does not.

### `skills/grit/dashboard.html` — a polling view

No build step, no framework, no dependencies. Themes are CSS variable blocks; adding one means a block here and a name in `THEMES`.

The concept grid is ordered by what needs work — learning first, highest score first inside a level — and every card that is not `shipped` carries the one sentence saying what would prove it, derived in `score.py` beside the level itself so the card and the arithmetic cannot disagree. Cards also count down to the point where their evidence starts halving, because ageing is the only way the score moves without the user failing anything.

It **polls**: the writer is a hook process that exits immediately and has nowhere to hold a connection, so files are the handoff and a 30-second timer plus a focus listener is the refresh. It also **degrades per panel** — one failing endpoint used to reject the whole `Promise.all` and blank every tile at its static zero, which made the product look entirely broken when one route was. Now a dead endpoint names itself in the header.

### `skills/grit/tutorial.template.html` — the page the assistant fills in

One file, no build step, no network beyond loopback. The check and the tool's own self-test are `text/plain` blocks evaluated together at worker scope, so the self-test can reach whatever the check defines and the user's code can never see the tests.

Three capabilities are declared by the authored check rather than switched on centrally, which is what keeps a tutorial written before any of them existed working unchanged:

| Declared by | Effect |
|---|---|
| `frames` on the check's return | the page renders a step-through above the result — `{label, cells, note}` per step, changed cells highlighted. Data only: the worker cannot hand the page markup |
| `IS_SOURCE_TEXT` at worker scope | the page stops requiring a JS function called `solve` and passes the textarea verbatim, so the exercise can be assembly, a query, a grammar. The *check* is still JS |
| the `PREDICTION` slot | a prediction asked before the first run and locked by it. It rides along with gate 2 and is judged with the answer — the one field on the page that cannot be written after seeing the result |

### The supporting scripts

- **`doctor.py`** — enumerates every place a hook registration can hide, resolves the script path, and *runs each command* to see whether it returns the blocking exit code. Ships inside the skill so `/grit` works without the repo.
- **`bin/install.sh`** — installs to 31 runtimes; wires hooks only where a `PreToolUse` mechanism exists (Claude Code, zrb). Merges config, never overwrites, backs up first, and **verifies its own work**: the daemon, scoring and hook self-checks must all pass or it exits non-zero. `check_docs.py` runs too, but only warns — drifted prose should not block an install.
- **`bin/_wire_hook.py`** — the two config shapes, kept out of the shell.

## Invariants

Break any of these and the record stops meaning anything. Each has a test, and each was once broken.

1. **`earned` is derived, never assigned** — all three gates present, check still passing, judgment sound. One function, one place.
2. **No raw credential enters the ledger.** `/ledger` is readable; rows carry an opaque `sid`.
3. **A failure is recorded, not swallowed.** A judged-unsound tutorial writes a failure event. It used to write nothing, so a failed attempt left an empty profile.
4. **`--failed` reaches the file.** It once mutated the returned dict *after* the write, so a recorded failure scored as a pass — raising the number it was meant to lower.
5. **A hook can never block an edit.**
6. **Gate 3 appends.**
7. **Every endpoint the dashboard fetches must answer.** The test derives the list from `dashboard.html` itself, so it cannot drift.

The self-checks that pin these, and how to run them, are in [AGENTS.md §2](../../AGENTS.md#2-run-it-do-not-reason-about-it). What is deliberately not built is [DESIGN.md §2](DESIGN.md#2-scope).
