# ADR 0012 — A hook must fail open, and the guard belongs in the registration

- **Status**: Accepted
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: hooks, integrity, availability, installer

## Context

`hooks/grit-hook.py` has always carried this constraint in its docstring:

> *It must never block editing because it broke. Any error at all: exit 0.*

It was enforced by wrapping `main()` in `try/except` and calling `sys.exit(0)`. That guard covers every failure **inside** the script and none of the failures that stop it from starting.

The gap is not theoretical. Both runtimes read **exit code 2** as *block this tool call* (zrb: `src/zrb/llm/hook/manager.py:348`; Claude Code documents the same). And:

```
$ python3 /nonexistent/hook.py ; echo $?
2
```

Python's "cannot open file" exit code *is* the block code. So a registration pointing at a script that is missing, moved, renamed, or unreadable does not degrade — it **fails closed**, blocking every `Write` and `Edit` in that project, reported as a Python `FileNotFoundError` that looks like a language problem rather than a hook problem.

This shipped and cost a working session. The repository's own README contained a copy-paste block that wrote `.zrb/hooks.json` containing the literal placeholder `/ABSOLUTE/PATH/TO/grit/hooks/grit-hook.py`, inside a **quoted** heredoc so nothing expanded. Following the documentation produced a config that blocked every file write, indefinitely, with no diagnostic pointing at grit.

The severity is asymmetric in the worst direction. A hook that fails open loses a measurement. A hook that fails closed stops the user working, and grit's entire value is one line in a log file — never worth a broken editor.

## Decision

> We will guard every hook registration so it cannot return a blocking exit code, and we will generate registrations rather than ask anyone to paste a path.

Every registration the installer writes is:

```
python3 '<absolute path>' || exit 0
```

Three properties follow:

1. **`|| exit 0` makes the whole failure class impossible** — missing file, wrong interpreter, syntax error, permission denied. grit signals decisions through JSON on stdout and never through exit codes, so it forfeits nothing.
2. **Shell form with a quoted path**, not exec form. Exec form (`command` + `args`) is immune to spaces in paths but cannot carry the guard; `shlex.quote` handles spaces, so shell form is strictly better here.
3. **No placeholder ever reaches a user.** `bin/install.sh --here` writes project-scoped config with the real absolute path filled in. The copy-paste block is deleted.

And because a broken registration is invisible until someone reads JSON by hand, **`skills/grit/doctor.py`** enumerates every site a registration can hide (claude user/project, zrb user/project), resolves the script path, and *actually executes each command* to check whether it returns 2. It ships inside the skill, so `/grit` can run it without the repository present.

## Consequences

- **A hook can no longer stop anyone working.** Pinned by `hooks/test_hook.py` property 13, which asserts the unguarded form really does exit 2 (the precondition) and that the guard turns it into 0.
- **A silently dead hook is now the failure mode** — it records nothing and says nothing. That is the correct trade against blocking, and `doctor.py` exists to make it visible on demand.
- **The guard is in the registration, not the script**, so it protects failures the script can never catch. Anything generating a registration by another route must reproduce it; the doctor flags an unguarded entry as `risky` even when it currently works.
- **The lesson generalises, and it is the same one as ADR 0011.** A guarantee was written in a docstring, tested only where it was already true, and shipped false. Every defect this project has had lives at the seam where code meets a real runtime: a variable expanded away by a skill loader, a relative path that only resolves in one runtime, a CSS origin conflict, an exit-code collision. Unit tests saw none of them.

## Alternatives Considered

- **Fix the README placeholder and change nothing else** — rejected. It addresses one instance of a class. Any stale path, from any source, reproduces the outage.
- **Catch it inside the script** — impossible by construction. The script is not running.
- **Register an absolute path and validate at install time** — necessary but insufficient: the installer already verified, and the path still went stale afterwards when files moved.
- **Use exec form to avoid shell quoting entirely** — rejected; it cannot carry the guard, and path-with-spaces is a smaller risk than fail-closed.

## Backlinks

- [ADR index](index.md)
- [ADR 0011 — Two credentials per session](0011-two-credentials-per-session.md)
