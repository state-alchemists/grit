# Dev fixtures

Things that exist to exercise the runtime during development. **None of these belong in user-facing docs or UI** — they look like features and behave like props.

---

## Running the daemon on a throwaway root

```sh
python3 skills/grit/serve.py --root /tmp/grit-scratch --port 0
```

`--port 0` takes any free port; the real one is written to `<root>/daemon.json`. Useful for poking at the dashboard and the preferences without touching your real `~/.grit`.

One caveat: project state — the authorship log, snapshots and the per-project off marker — lives under the **same** root (`<root>/projects/<key>/`, keyed by the project's real path). A throwaway root starts with an empty project list and stays empty unless the hook is also writing there (`GRIT_ROOT=/tmp/grit-scratch`). So `/authorship` and `/tasks` on a scratch root show nothing — that is the fixture working, not the dashboard broken.

The self-checks are not props; they are listed in [AGENTS.md §2](../../AGENTS.md#2-run-it-do-not-reason-about-it).
