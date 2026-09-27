# Grit — Test Strategy

## Testing Levels
| Level | Scope | Tool | Target |
|-------|-------|------|--------|
| Unit | The scoring model | `python3 skills/grit/score.py selftest` (stdlib asserts) | 10 scoring properties, each a defect that shipped |
| Unit | The validity-study analysis | `python3 bin/test_study_report.py` | 5 study_report properties |
| Integration | The hook fired as a runtime fires it, `verify_edit.py` against real git repositories, the installer's registrations | `python3 hooks/test_hook.py` | 26 hook properties |
| Integration | The daemon started for real, every route the dashboard fetches | `python3 skills/grit/test_serve.py` | 7 integrity properties |
| Docs | Every checkable claim in the documentation against the code | `python3 bin/check_docs.py` | 13 classes of claim, 0 findings |
| Machine | This machine's hook registrations, each actually executed | `python3 skills/grit/doctor.py` | No registration that can block |
| E2E | Real installer, registered hooks, the skill's commands in the order it prescribes | By hand, in a sandbox | Before any change to installation or the scoring loop — not automated |

## Test Naming Convention
- A test is a **property**, named for what breaks if it fails: `_property_<what must hold>` in `hooks/test_hook.py` and `skills/grit/test_serve.py`, `_check_<what must hold>` in `score.py selftest` and `bin/test_study_report.py` — never `test_record_3`.
- Each case carries a comment naming the defect that shipped; that comment is not stripped for terseness.

## CI Gates
There is no CI. The gates are the installer's own verification, which runs on every install.

| Gate | Trigger | Command | Blocking |
|------|---------|---------|----------|
| Daemon self-check | `bin/install.sh` | `python3 skills/grit/test_serve.py` | Yes |
| Scoring self-check | `bin/install.sh` | `python3 skills/grit/score.py selftest` | Yes |
| Hook self-check | `bin/install.sh`, where a hook is wired | `python3 hooks/test_hook.py` | Yes |
| Docs | `bin/install.sh` | `python3 bin/check_docs.py` | No — warns; drifted prose should not block an install |
| Traceability | By hand | `python3 .sdlc/tools/sdlc-validate.py --strict` | No — the project has no specs yet |

## Environments
| Env | URL | Deploy | Data |
|-----|-----|--------|------|
| Developer machine | `http://127.0.0.1` on the port in `~/.grit/daemon.json` | `bin/install.sh` | Real — the user's own `~/.grit/`; the suites use temporary roots |

## Quality Goals
- **Regression coverage**: every fix lands with a property that fails without it.
- **Docs**: `check_docs.py` reports no stale claim.
- **Known gap**: no automated end-to-end run. Every suite once passed while no task done through the skill could score; only a sandboxed end-to-end run showed it.
