# AGENTS.md

Conventions for working in this repository that you **cannot get by reading the code**. Everything inferable from the source is deliberately absent — for what the product is read [README.md](README.md), for how it works read [.sdlc/docs/ARCHITECTURE.md](.sdlc/docs/ARCHITECTURE.md), for why it is shaped this way read [.sdlc/docs/adr/](.sdlc/docs/adr/README.md).

---

## 1. The rules that are not negotiable

**The skill never mentions ADRs.** `skills/grit/SKILL.md`, `skills/grit/dashboard.html`, `skills/grit/tutorial.template.html`, and every error message and screen the user sees. Decision records are internal engineering history for contributors; citing one at a user is leaking your own filing system into their product. Explain the *reason* if it matters, drop it if it doesn't. This is checked by hand — nothing enforces it, so check before you ship.

**Markdown is never hard-wrapped.** One line per paragraph, however long. Hard wraps make every subsequent edit a noisy multi-line diff. Do not reflow a file to 80, 95, or any other column, and do not "tidy" a long line you happen to be editing near.

**Skill text uses literal paths, never shell variables.** Some runtimes (zrb among them) expand `$VAR` inside skill text before the model ever sees it, so a `$HOME` written in `SKILL.md` arrives as an empty string and the command silently points at the filesystem root. Write `~/.grit/daemon.json`, never `$HOME/.grit/daemon.json`. The same applies to scripts the skill tells the assistant to run: prefix them `<skill-dir>/`, because a relative path resolves differently in each runtime.

**No new dependencies.** Python standard library only, no framework in the HTML, no build step. `dashboard.html` is opened by a browser exactly as it sits on disk. If something needs a package, it is probably not worth having.

**Never claim skill gain.** The supportable claim is *harm avoidance*; no study shows a tool making anyone better than working unaided. This governs the README, the skill, commit messages and anything on screen. Overclaiming here makes the product indistinguishable from the problem it treats.

**`bin/install.sh` must run on bash 3.2** — that is what ships on macOS. No associative arrays, no `${x,,}`, no `mapfile`.

---

## 2. Run it. Do not reason about it.

Almost every defect in this repository's history was found by executing something, and missed by reading it. Reading finds the bug you were already looking for.

```sh
python3 skills/grit/test_serve.py      # 13 integrity properties
python3 hooks/test_hook.py             # 19 hook properties
python3 skills/grit/score.py selftest  # 18 scoring properties
python3 skills/grit/doctor.py          # this machine's hook registrations
python3 bin/check_docs.py              # every checkable claim in the docs
```

Specific forms of this that have each cost real time:

- **Quoting a number in prose? Compute it first.** `SKILL.md` once put a tutorial's ceiling at `0.4` and kept saying so through a change that halved every weight, because that figure was never anything but a sentence. Running the model gave `0.30`. (`check_docs.py` now computes it — and it flagged this very bullet when the sentence was phrased as a live claim, which is the check working.)
- **Writing a copy-paste block? Paste it.** A README block once contained a literal `/ABSOLUTE/PATH/TO/` placeholder inside a quoted heredoc. Pasting it registered a hook pointing at a nonexistent script, and a missing script makes Python exit `2` — which both runtimes read as *block this tool call*. It broke every file write in the user's project.
- **A browser fetch is not a DOM dump.** Headless Chrome's `--dump-dom` returns before `fetch()` resolves, so a working dashboard reads as blank. Check the endpoints with `curl`, or check the page with something that actually waits.
- **`str.replace` returns silently when nothing matched.** Every scripted edit asserts its anchor first: `assert old in s, "ANCHOR NOT FOUND"`. This has quietly produced no-op "fixes" more than once.

**Do not deliver broken product.** If you changed installation, run the installer. If you changed the daemon, start it and hit the routes.

---

## 3. Comments

A comment earns its place by **changing what the next edit does**. Keep the non-obvious constraint; cut the war story.

```python
# keep — a future editor would otherwise re-break this
# hashlib, not hash(): Python salts hash() per process, so two invocations
# would never agree on the same content.

# cut — this belongs in an ADR, and does
# This was the worst gap in the loop: a user could pass the check, submit a
# justification, be judged unsound — and end with a completely empty profile...
```

**The test files are the deliberate exception.** Every case in `test_serve.py`, `test_hook.py` and `score.py selftest` is a defect that actually shipped, and the comment names which one. That comment is the point: it is what makes a future edit that reintroduces the bug fail *loudly* instead of quietly re-earning concepts nobody earned. Never strip them for terseness.

New tests follow the same shape. A test here is a **property**, named for what breaks if it fails — not `test_record_3`.

**Define the caller before the callee, where practical.** Read top to bottom, entry point first, in the order the code actually runs. This was briefly an AST checker under bin/, deleted for enforcing pure taste with a 168-line call-graph walker that drove a whole rewrite and wasn't wired into anything. Keep the convention, drop the tooling — this is a code-review preference, not a build gate, and "where practical" means mutual recursion and shared helpers are exempt.

**Names follow the A/HC/LC cheatsheet** ([kettanaito/naming-cheatsheet](https://github.com/kettanaito/naming-cheatsheet)): `prefix? + action + high context + low context`. Every function name carries an action verb or a boolean prefix — `_get_project_dir`, `_is_duplicate`, `_compose_authorship_row`, `_report_unverified` — never a bare noun (`_state`, `_store`, `_duplicate` are all past mistakes that got renamed). Booleans read as predicates (`is`/`has`/`should`). No contractions in identifiers (`get_preferences`, not `_prefs`). Prefer `compose`/`get`/`set`/`report`/`resolve` for pure data-shaping, and keep JSON API keys (`hook_active`) untouched by function renames.

---

## 4. Documentation

**Each layer has exactly one owner.** Writing a fact into a second file is how the two come to disagree, and then nobody can tell which is wrong.

| Layer | Owner |
|---|---|
| Conventions for working here | [AGENTS.md](AGENTS.md) |
| What it is, how to install | [README.md](README.md) |
| The mechanism — processes, files, data path, invariants | [.sdlc/docs/ARCHITECTURE.md](.sdlc/docs/ARCHITECTURE.md) |
| The principles and what is unproven | [.sdlc/docs/DESIGN.md](.sdlc/docs/DESIGN.md) |
| Individual decisions and rejected options | [.sdlc/docs/adr/](.sdlc/docs/adr/README.md) |
| What the assistant does at runtime | [skills/grit/SKILL.md](skills/grit/SKILL.md) |
| Props that look like features but are not | [.sdlc/docs/dev-fixtures.md](.sdlc/docs/dev-fixtures.md) |

Before adding a document, find the one that already owns that layer. `ARCHITECTURE.md` exists because `DESIGN.md` had drifted into documenting files no code wrote — `profile.json`, `tasks.json`, `checks/`, `missions/` — while never mentioning the two that carried all the real data.

**Decline a generated rules or conventions file under `.sdlc/`.** Tooling offers to write one; it is a second owner for the first row. Point the tool at AGENTS.md instead.

**A claim in a doc should be one `bin/check_docs.py` can verify.** It checks twelve classes: paths, links, runtime files, routed endpoints, CLI flags, scoring constants, verdict names, test counts, **computed values**, **cross-doc agreement**, **ADR existence**, and ADR statuses. When you fix a stale claim, ask whether a checker class would have caught it — and if not, add one. The last three classes exist because a prose number, a disagreement between two files, and a citation to a renumbered ADR each slipped past everything else.

---

## 5. Decision records

- **Numbers run in reading order, not chronological order.** All of it was decided in one pass, so chronology carries no information and a number that tells you where to start does.
- **A superseded decision does not keep its own file.** Fold it into the ADR that replaced it, as a rejected alternative stating why it failed and what survived. Then delete it. Reasoning is only useful next to the decision that overruled it, and git keeps the original.
- **Deferred is not superseded.** [ADR 0011](.sdlc/docs/adr/0011-routing-on-a-measured-profile-deferred.md) describes a router and a battery that nothing implements — it stays, in full, because deleting it invites someone to reinvent a design that was already argued down. Delete an ADR only when acting on it would now be *wrong*, never because it is unbuilt.
- **Renumbering breaks citations in code too.** `.py` and `.sh` files cite ADRs. Class 8d of `check_docs.py` now catches a dead one.

---

## 6. What the repository is strict about, and why

This product argues that a record which can be edited proves nothing. That applies to working on it, not just to using it.

- **`~/.grit/evidence.jsonl` and the ledger are append-only.** The remedy for a wrong record is a new measurement, never an edit — including when the mistake was the assistant's. That is the exact case an audit trail exists for.
- **`earned` is derived in one function and assigned nowhere.** Two code paths that both decide what a word means will eventually disagree, invisibly.
- **A hook can never block a tool call.** Every registration carries `|| exit 0` — see [ADR 0007](.sdlc/docs/adr/0007-hooks-must-fail-open.md).
- **Never upgrade a verdict.** `UNVERIFIED` is not a synonym for `HUMAN-WRITTEN`.

---

## 7. Open, and deliberately not decided

- **Where hand-authored tutorials should live.** Today only `~/.grit/tutorials/`, which is right for the planned generate-on-demand design and wrong for the hand-authored reality — a tutorial someone wrote is not in version control anywhere. Go's call.
- **Splitting `skills/grit/serve.py`.** It is long. Offered, not authorised; do not do it unsolicited.
