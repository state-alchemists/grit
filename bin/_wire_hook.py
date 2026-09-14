#!/usr/bin/env python3
"""Register or unregister grit's PreToolUse hook. Called by bin/install.sh.

Two runtimes, two config shapes, one job:

  claude  ~/.claude/settings.json   nested: {"hooks": {"PreToolUse": [ ... ]}}
  zrb     ~/.zrb/hooks.json         flat array: [ {"name", "events", ...} ]

Both files belong to the user and usually hold other things, so every edit here
is a merge, never an overwrite: back up first, remove only entries we recognise
as ours, and leave a file we emptied no worse than we found it.

Usage: _wire_hook.py <claude|zrb> <config-path> <hook-path> <install|remove>
"""

import json
import os
import shlex
import shutil
import sys

MARKER = "grit-hook.py"      # how we recognise our own entries on re-run


def guarded(hook_path):
    """The command to register, wrapped so it can never block a tool call.

    Python exits 2 when it cannot open a script file, and 2 is exactly the exit
    code both zrb and Claude Code read as "block this tool call" — so a missing
    or renamed script fails CLOSED, killing every Write and Edit in the project.

    `|| exit 0` covers the whole class: missing file, wrong interpreter, syntax
    error. grit signals through JSON on stdout, never exit codes, so it gives up
    nothing (ADR 0007).

    The path is shell-quoted, which is why shell form is safe here despite
    spaces — exec form would be immune to spaces but cannot carry the guard.
    """
    return "python3 " + shlex.quote(hook_path) + " || exit 0"


def _load(path):
    if not os.path.exists(path):
        return None
    shutil.copy2(path, path + ".grit-backup")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        print("  %s is not valid JSON — leaving it alone" % path,
              file=sys.stderr)
        sys.exit(3)


def _write(path, data, empty):
    """Write, or delete the file if we emptied something we alone populated."""
    if data == empty and os.path.exists(path):
        os.remove(path)
        for leftover in (path + ".grit-backup",):
            if os.path.exists(leftover):
                os.remove(leftover)
        print("  removed     %s (it held nothing else)" % path)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def claude(path, hook, action):
    data = _load(path)
    if data is None:
        data = {}
    hooks = data.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])

    def ours(group):
        # Match on args too: the handler moved from shell form
        # ("python3 /path/grit-hook.py") to exec form ("python3", ["/path/..."]),
        # and an upgrade must still recognise the entry it is replacing.
        return any(MARKER in h.get("command", "")
                   or any(MARKER in a for a in h.get("args", []))
                   for h in group.get("hooks", []))

    pre[:] = [g for g in pre if not ours(g)]
    if action == "install":
        # Exec form (`args` present): the docs recommend it whenever the hook
        # references a path, because each element is passed as one argument
        # with no quoting — shell form would break on a path containing spaces.
        handler = {"type": "command", "command": guarded(hook), "timeout": 5}
        pre.append({
            # Real edits: recorded exactly, and they trigger the one prompt.
            "matcher": "Write|Edit|NotebookEdit",
            "hooks": [handler],
        })
        pre.append({
            # Shell calls: recorded as opaque. Without this, an assistant that
            # writes through `python3 - <<EOF` or `sed -i` leaves no trace and
            # the work reads as human-written.
            "matcher": "Bash|PowerShell",
            "hooks": [handler],
        })
    if not pre:
        hooks.pop("PreToolUse", None)
    if not hooks:
        data.pop("hooks", None)
    _write(path, data, empty={})
    return data


def zrb(path, hook, action):
    data = _load(path)
    if data is None:
        data = []
    if not isinstance(data, list):
        print("  %s is not a hook array — leaving it alone" % path,
              file=sys.stderr)
        sys.exit(3)

    data[:] = [h for h in data if h.get("name") != "grit-authorship"]
    if action == "install":
        data.append({
            "name": "grit-authorship",
            "description": "Record who wrote the code; offer self-completion once a session.",
            "events": ["PreToolUse"],
            "type": "command",
            "matchers": [{"field": "tool_name", "operator": "regex",
                          "value": "^(Write|Edit|NotebookEdit|Bash|PowerShell)$"}],
            "config": {"command": guarded(hook), "shell": True},
            "timeout": 5,
        })
    _write(path, data, empty=[])
    return data


def main():
    runtime, path, hook, action = sys.argv[1:5]
    handler = {"claude": claude, "zrb": zrb}[runtime]
    handler(path, hook, action)
    if os.path.exists(path):
        print("  %s  %s" % (
            "registered" if action == "install" else "unregistered", path))


if __name__ == "__main__":
    main()
