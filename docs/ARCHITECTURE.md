# Architecture

How grit actually works, end to end — **the mechanism**.

For the principles that constrain it and the limits it has not escaped, see [DESIGN.md](DESIGN.md). For individual decisions and what was rejected, see [`adr/`](adr/README.md).

---

## The one-sentence version

A hook watches who writes code, git says what changed, and a local daemon turns those two facts plus your own justification into a per-concept level you did not award yourself.

## Three processes, and they barely know each other

| Process | Lives for | Writes | Never does |
|---|---|---|---|
| **the hook** (`hooks/grit-hook.py`) | milliseconds, once per tool call | `<project>/.grit/authorship.jsonl` | talk to the daemon, block an edit |
| **the assistant** (`skills/grit/SKILL.md`) | your session | evidence, via `score.py` | decide the check passed |
| **the daemon** (`skills/grit/serve.py`) | until stopped | `~/.grit/*` | run your acceptance check |

They are deliberately not coupled. The hook cannot depend on the daemon running, or every file edit would inherit the daemon's uptime. The daemon cannot depend on the hook, or a fresh machine could not render a dashboard. They meet through files.

## The files, and which one is the truth

Everything is JSON or JSONL on disk. There is no database and no server you do not control.

```
<project>/.grit/                     per project — raw observation
  authorship.jsonl    append-only    every byte the assistant wrote, here
  snapshots/<task>.json              the git baseline for one handover
  off                 marker         killswitch for this project

~/.grit/                             per person — the record
  evidence.jsonl      append-only    THE SOURCE OF TRUTH for your score
  ledger.json         replace        tutorial sessions and their three gates
  sessions.json       replace, 0600  live tokens; survives a daemon restart
  preferences.json    replace        theme, callsign — configuration only
  projects.json       replace        which projects have an authorship log
  daemon.json         replace        where the daemon is listening right now
  tutorials/          files          hand-authored tutorial pages

  asked/              markers        one file per session already prompted
  .last-event         replace        2-second de-dup window for the hook
  hook-errors.log     append-only    the hook never raises; it logs and exits 0
  daemon.log          append-only    stdout/stderr when started with --daemon
```

The four below the gap are scratch, not record: delete any of them and nothing about your score changes.

**`evidence.jsonl` is the only file that matters.** The score is recomputed from it on every read and stored nowhere, so there is no cached number to go stale and nothing to edit into being true. Delete it and your score is genuinely gone; edit it and you have only lied to yourself.

The split is deliberate: **observations are per project, proficiency is per person.** Learning token buckets in one repository does not un-learn them in the next.

## The path a score takes

```mermaid
flowchart TD
    subgraph OBSERVE ["① Observation — automatic"]
        W["assistant calls Write / Edit"] -->|PreToolUse| H["grit-hook.py"]
        B["assistant calls Bash"] -->|PreToolUse| H
        H --> H1["append authorship.jsonl<br/>edits: exact lines · shell: opaque"]
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
        CALC --> LV["unproven → recall → proven"]
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

Runs as a `PreToolUse` command hook. Two jobs: append an authorship row, and ask once per session whether you would rather do it yourself.

Three properties it must never lose, each of which was once broken:

- **It cannot block an edit.** Python exits `2` when it cannot open a script, and `2` is exactly the code both runtimes read as *block this tool call*. Every registration is therefore `python3 '<path>' || exit 0` — see [ADR 0007](adr/0007-hooks-must-fail-open.md).
- **Shell calls are recorded as `opaque`, never as zero.** An assistant editing through `python3 - <<EOF` produces no edit event; recording nothing would let that read as human-written.
- **One event, one row.** Two registrations can match one edit (user-level plus project-level, or zrb reading Claude's settings). A 2-second content hash de-duplicates.

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

```
credit = source_weight × assistance × novelty     (capped, summed, max 1.0)
```

- **source** — repo `0.5`, sandbox `0.2`
- **assistance** — none `1.0`, partial `0.5`, full `0.0`
- **novelty** — `1/(1+repeats)`, hard-capped at `1.5 × weight` per distinct task

`proven` needs `≥ 0.80` **and two distinct unaided repository tasks**. Failures subtract `0.25`; evidence older than 90 days counts half.

A task's identity is `(source, project, task)` for repository work and `(source, task)` for tutorials — repository task ids are per-project sequences, so `001` in two repos is two tasks, while a tutorial is the same exercise wherever it runs. Full reasoning and the calibration errors that were caught by running it: [ADR 0009](adr/0009-graded-score-from-capped-evidence.md).

### `skills/grit/serve.py` — the daemon

Localhost only, no cross-origin. Three responsibilities: serve the dashboard and tutorials, own the three-gate ledger, and expose the score.

| Route | Returns |
|---|---|
| `/` | the dashboard (read from disk per request — no restart needed to edit it) |
| `/status` | everything `/grit` needs in one call |
| `/score`, `/profile` | per-concept levels |
| `/authorship` | assistant-written lines per project |
| `/tutorials`, `/ledger`, `/preferences`, `/themes`, `/health` | as named |
| `POST /tutorial/<report-token>/{check,justification}` | gates 1 and 2 |
| `POST /judgment/<judge-token>` | gate 3 |

**Two credentials per session.** The page gets a *report* token and can only report gates 1 and 2. The *judge* token is printed to the daemon's terminal and never reaches the browser; `POST /tutorial/<report>/judgment` returns `403` on purpose. Without the split the page could award itself a pass with one `fetch()` — [ADR 0006](adr/0006-two-credentials-per-session.md).

**Gate 3 appends.** The first verdict stands; later calls return `409` with the standing verdict and the full history, and change nothing. A verdict you can overwrite is not evidence.

Editing `serve.py` needs a daemon restart. Editing `dashboard.html` does not.

### `skills/grit/dashboard.html` — a polling view

No build step, no framework, no dependencies. Themes are CSS variable blocks; adding one means a block here and a name in `THEMES`.

It **polls**: the writer is a hook process that exits immediately and has nowhere to hold a connection, so files are the handoff and a 30-second timer plus a focus listener is the refresh. It also **degrades per panel** — one failing endpoint used to reject the whole `Promise.all` and blank every tile at its static zero, which made the product look entirely broken when one route was. Now a dead endpoint names itself in the header.

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

## Running the checks

```sh
python3 skills/grit/test_serve.py      # daemon integrity
python3 skills/grit/score.py selftest  # the scoring model
python3 hooks/test_hook.py             # the hook
python3 skills/grit/doctor.py          # this machine's registrations
python3 bin/check_docs.py              # the docs against the code
```

No framework. Every case is a defect that actually shipped, and the comment says which — so a future edit that reintroduces one fails loudly instead of quietly re-earning concepts nobody earned.

## What is not built

**Tutorial generation.** The runtime delivers and scores a tutorial; nothing writes one. Every score today comes from real repository tasks. The onboarding battery and the router are deferred — [ADR 0009](adr/0009-graded-score-from-capped-evidence.md) removed the need for them to exist before anything can be scored, and [ADR 0011](adr/0011-routing-on-a-measured-profile-deferred.md) records what they would be if built.

And the honest ceiling, unchanged: this may **avoid harm**. Whether a `proven` concept predicts real capability has never been tested. That study is [ADR 0012](adr/0012-profile-validity-is-the-critical-path.md), and it is still unrun.
