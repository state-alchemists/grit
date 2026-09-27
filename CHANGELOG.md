# Changelog

What changed, newest first. Summaries only — the reasoning is in the commit messages and the [decision records](.sdlc/docs/adr/README.md). Grit has no version numbers yet, so entries are dated by merge.

## Unreleased

### Added
- **A router, as one rule.** `score.py level <concept>...` pre-selects *guided* only where a failure was recorded on a concept still at `learning`, and *solo* everywhere else, including concepts nobody has measured. The skill runs it before offering.
- **A weekly trend** on the tasks panel: the last 8 weeks of "you wrote" vs "assistant helped", from `/tasks`.
- **Tasks you took on.** `verify_edit.py verify` appends each verdict to `~/.grit/projects/<key>/tasks.jsonl` with git's lines added, removed and files changed; the dashboard shows the latest per task and totals per verdict (`/tasks`).
- **`PostToolUse` registration.** The hook records an `applied` row when an edit actually ran, so "you took over" is observed rather than inferred. Re-run `bin/install.sh` to pick it up; older installs fall back to the inference.
- **A setting for the default choice** (solo or hand-off). Previously settable only by editing JSON.
- **Beginners get a practice repository.** "Teach me X, I have no experience" now means a small repository with the real toolchain and a failing test, scored like any repository work.

### Fixed
- **Every task done through the skill came out UNVERIFIED and scored zero** on Claude Code. The skill has the assistant run the user's check and `verify_edit.py` itself through the shell, and every shell call after the snapshot was unobservable. The hook now fingerprints the working tree around each shell call and records which files it wrote; a call that wrote nothing no longer voids the task, one that wrote files makes it ASSISTED and names them, and verify excuses only its own in-flight call. Found by simulating a full session end to end; your real `~/.grit` held 3 evidence rows, all recorded by hand.
- **Distinct shell calls merged into one row.** The dedupe fingerprint ignored the command, so shell calls under 250ms apart — any parallel batch — were dropped; one simulated session lost 3 of its 5. It now keys on `tool_use_id` and the command.
- **"You took over" was always 0.** The hook logged the edit that raised the once-per-session offer as an assistant edit in the same session, so no offered session could ever count as taken. That edit is now flagged `prompted` and excluded, and shell calls no longer count against it (in DIY mode the assistant still runs your tests). Pinned by a new hook property.
- `serve.py --daemon` crashed on a fresh machine: it opened `daemon.log` before creating `~/.grit`, so the README's first dashboard command failed until something else had made the directory. Pinned by a new daemon property.
- `verify_edit.py` mis-split untracked filenames containing spaces.
- `verify_edit.py` no longer counts the hook's own `offered` rows as assistant-written files.
- `score.py selftest` printed a hard-coded "21 properties" over nine checks; it now prints what ran (9). `bin/test_study_report.py` likewise.
- The `mechanism-off` notice claimed nothing was being offered while the hook still offered; it now says only what is true.
- `SKILL.md` asked two different three-way questions in a row, with "You do it" meaning the user in one and the assistant in the other. There is now one menu.

### Changed
- **Levels renamed** `unproven → recall → proven` to **`learning → practised → shipped`**, and the menu to **solo / guided / hand-off**. A level names the evidence, not the person, and "shipped" is exactly what the top level requires. Levels are derived on every read, so no data changes — but `/score`'s `headline` keys are now `shipped` and `practised`, and `score.py`'s constants are `PRACTISED_AT`, `SHIPPED_AT` and `SHIPPED_NEEDS_UNAIDED_TASKS`.
- `bin/check_docs.py` checks each quoted test count against the suite named on its line (it accepted any suite's number, and flagged METR's "20 setting properties"), and gains a class for the hook's de-dup window, which four docs quoted as 2 seconds against 250ms in code. The failure penalty and stale weight are now named constants it verifies.
- One owner for shared logic: the skill's project-key derivation lives in `verify_edit.py` (the hook keeps its pinned copy, since it installs apart from the skill); `_wire_hook.py` takes its registration markers from `doctor.py`; `serve.py` reads optional JSON through one helper and uses `html.escape`.
- Docs: the README states what works once instead of five times, and test commands live only in AGENTS.md. Stale claims in ADRs 0003–0008 corrected. LANDSCAPE's retracted "gaps" folded into one section.

### Removed
- **Tutorials, and everything that existed only for them** — the tutorial template, the sandbox evidence source, the ledger, the three gates, the report and judge credentials, `sessions.json`, and the `/tutorials`, `/ledger`, `/tutorial/…` and `/judgment/…` routes ([ADR 0003](.sdlc/docs/adr/0003-repository-work-is-the-only-evidence.md), which folds in the former 0003–0006). On the one machine with real usage they had produced no score, and simulating one showed its judgment step was unreachable as instructed. Existing `"source": "sandbox"` rows stay in `evidence.jsonl` and now score nothing; the old `ledger.json`, `sessions.json` and `tutorials/` are left on disk, unread.
- The `pace`, `depth` and `format` preferences — `pace` was never read, the other two only by tutorials.
- `.sdlc/docs/USAGE.md` — a walkthrough of the abandoned per-mission design; nothing in it described the product. Git keeps it.
- Dead code: `State.get_session`, `score.LEVELS`, the dashboard's `RANK`, a duplicate HTML writer, and an unused `/profile` fetch on every refresh.

## 2026-09-20 — tutorials that teach, and beginners served (#4)
- Tutorials can return a step-through trace, accept non-JavaScript source (the check stays JS), and ask for a prediction before the first run, locked once you run and judged with the justification.
- The skill serves "teach me X, I have no experience" with sandbox exercises: the exclusion is the absence of an oracle, not the absence of a repository. Sandbox work tops out at `recall`.
- Uninstall no longer removes the runtime's `skills/` directory, and says that `~/.grit` survives.

## 2026-09-20 — audit fixes (#3)
- `verify_edit.py` errors exit 64 instead of sharing a code with a verdict, which had scored mistyped task ids as assisted or unchanged.
- Default port is 4748; the daemon publishes its real address to `~/.grit/daemon.json`.
- `check_docs.py` gains computed values, cross-doc agreement, ADR and section citations, and discovers every `test_*.py`.

## 2026-09-20 — sdlc scaffolding (#2)
- Docs moved under `.sdlc/docs/`; the `sdlc-*` conventions, templates and validator installed.

## 2026-09-16 — one profile per person (#1)
- All state moved to `~/.grit/`; per-project observations live under `~/.grit/projects/<key>/`, keyed by a hash of the project's real path. A legacy `.grit/off` marker is still honoured.
- Naming convention applied across the code.

## 2026-09-13 – 09-15 — first version
- The hook, `verify_edit.py`, graded scoring, the three-gate daemon with two credentials per session, the dashboard, the installer, and the decision records.
