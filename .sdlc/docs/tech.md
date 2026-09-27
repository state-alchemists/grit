# Grit — Technology Overview

## Stack
| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language (hook, scoring, daemon, tests) | Python, standard library only | Python 3 — no minimum declared or tested | Runs wherever the AI coding tool runs, with nothing to install |
| Language (skill) | Markdown `SKILL.md`, loaded by the AI coding tool | — | One skill directory serves 31 runtimes |
| Language (dashboard) | HTML, CSS and JavaScript in one file, no framework | — | Opened by a browser exactly as it sits on disk; no build step |
| Language (installer) | Bash | 3.2+ | What ships on macOS |
| Database | JSON and JSONL files under `~/.grit/` | — | Append-only files are the record; there is nothing to run or migrate |

## Architecture Principles
1. **A hook can never block a tool call** — every registration carries `|| exit 0`; a silently dead hook is the accepted failure mode ([ADR 0007](adr/ADR-0007-hooks-must-fail-open.md)).
2. **The record is append-only** — `evidence.jsonl`, `tasks.jsonl` and `authorship.jsonl` gain rows; nothing already written is altered or removed. The remedy for a wrong record is a new measurement.
3. **A level is derived in one function and stored nowhere** — `score_concept` decides it on every read.
4. **Processes meet through files** — the hook, the assistant and the daemon never depend on each other running ([ADR 0008](adr/ADR-0008-dashboard-polls-files-it-does-not-push.md)).
5. **Local only** — the daemon binds `127.0.0.1` and serves no cross-origin request; nothing is transmitted.

## Constraints
- No third-party dependency, no framework in the HTML, no build step.
- `bin/install.sh` must run on bash 3.2: no associative arrays, no `${x,,}`, no `mapfile`.
- Skill text uses literal paths (`~/.grit/daemon.json`), never shell variables, because some runtimes expand `$VAR` before the model sees it.
- The hook installs apart from the skill, so it keeps its own pinned copy of the project-key derivation.

## Dependencies
| Dependency | Purpose | License |
|------------|---------|---------|
| Python standard library | Everything that runs | PSF |
| git | Snapshots and diffs that decide who changed what | GPL-2.0 |
| An AI coding tool with a `PreToolUse` hook (Claude Code, zrb) | Fires the hook that observes authorship; other tools load the skill without it | per tool |
| A web browser | Renders the dashboard | per browser |

## Property-Based Testing
- None configured.
