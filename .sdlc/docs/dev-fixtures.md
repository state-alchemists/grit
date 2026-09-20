# Dev fixtures

Things that exist to exercise the runtime during development. **None of these belong in user-facing docs or UI** — they look like features and behave like props.

---

## Loading the tutorial template by hand

```sh
cp skills/grit/tutorial.template.html ~/.grit/tutorials/my-concept.html
```

This puts a row in the dashboard's tutorial list and lets you click through to the runtime: the session token injection, the report path, the sandbox worker, the justification box.

**What it is not: a tutorial.** Copied raw, the template contains its own placeholders:

| Slot | Renders as |
|---|---|
| `<!-- CONCEPT -->` | empty heading |
| the lesson body | three HTML comments — blank paragraphs |
| `CHECK_SOURCE` | `return { pass: false, message: "CHECK_SOURCE not implemented." }` |

The check **always fails**, by construction. So the page can never be completed, never writes a ledger entry, and never produces a profile entry.

That is fine for testing the plumbing and actively misleading as a user instruction — it was in the README and the dashboard's empty state, where it read as "here is how you get started" while handing the user something that cannot work. Removed from both on 2026-09-13.

If you want a tutorial that actually passes, you have to author the concept text and write a real differential test in the `check-source` block. Doing that per concept, by hand, is what the assistant actually does — see the tutorial section of the skill. It works; it is simply not automated, which is why this template exists as a starting point rather than a finished page.

## Running the daemon on a throwaway root

```sh
python3 skills/grit/serve.py --root /tmp/grit-scratch --port 0
```

`--port 0` takes any free port; the real one is written to `<root>/daemon.json`. Useful for poking at the tutorial runtime, the ledger and the preferences without touching your real `~/.grit`.

One caveat: project state — the authorship log, snapshots and the per-project off marker — lives under the **same** root (`<root>/projects/<key>/`, keyed by the project's real path). A throwaway root starts with an empty project list and stays empty unless the hook is also writing there (`GRIT_ROOT=/tmp/grit-scratch`). So `/authorship` on a scratch root shows nothing, even while `/ledger` is live — that is the fixture working, not the dashboard broken.

## The self-checks

```sh
python3 skills/grit/test_serve.py      # 14 integrity properties
python3 hooks/test_hook.py             # 20 hook properties
python3 skills/grit/score.py selftest  # 19 scoring properties
python3 bin/test_study_report.py       # 5 study_report properties
```

Every case in all three is a defect that actually shipped. Read the comments before changing one.
