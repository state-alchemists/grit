#!/usr/bin/env python3
"""Register or unregister grit's PreToolUse hook. Called by bin/install.sh.

Two runtimes, two config shapes, one job:

  claude  ~/.claude/settings.json   nested: {"hooks": {"PreToolUse": [...], "PostToolUse": [...]}}
  zrb     ~/.zrb/hooks.json         flat array: [ {"name", "events", ...} ]

Both files belong to the user and usually hold other things, so every edit here
is a merge, never an overwrite: back up first, remove only entries we recognise
as ours, and leave a file we emptied no worse than we found it.

Usage: _wire_hook.py <claude|zrb> <config-path> <hook-path> <install|remove>
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from typing import Any, Callable

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "grit"))
from doctor import MARKER, ZRB_HOOK_NAME  # noqa: E402 — one definition of "ours"

# One runtime's writer: takes (config path, hook path, action) and returns the
# merged config it wrote.
Writer = Callable[[str, str, str], Any]


def main() -> None:
    if len(sys.argv) != 5:
        # The docstring above promises a usage line, so running it by hand has
        # to produce one. Without this a bare call raises ValueError before any
        # message is printed, which looks like a broken install script.
        sys.stderr.write(
            "usage: _wire_hook.py <claude|zrb> <config-path> <hook-path> "
            "<install|remove>\n"
        )
        sys.exit(2)
    runtime, path, hook, action = sys.argv[1:5]
    handler: Writer = {"claude": claude, "zrb": zrb}[runtime]
    handler(path, hook, action)
    if os.path.exists(path):
        print(
            "  %s  %s" % ("registered" if action == "install" else "unregistered", path)
        )


def claude(path: str, hook: str, action: str) -> Any:
    data = _load_with_backup(path)
    if data is None:
        data = {}
    hooks = data.setdefault("hooks", {})
    wanted = _claude_entries(guarded(hook)) if action == "install" else {}
    for event in CLAUDE_EVENTS:
        groups = hooks.setdefault(event, [])
        groups[:] = [g for g in groups if not _is_ours(g)]
        groups.extend(wanted.get(event, []))
        if not groups:
            hooks.pop(event, None)
    if not hooks:
        data.pop("hooks", None)
    _write(path, data, empty={})
    return data


def _load_with_backup(path: str) -> Any:
    if not os.path.exists(path):
        return None
    shutil.copy2(path, path + ".grit-backup")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        print("  %s is not valid JSON — leaving it alone" % path, file=sys.stderr)
        sys.exit(3)


def _is_ours(group: dict[str, Any]) -> bool:
    """Match on args too: the handler moved from shell form
    ("python3 /path/grit-hook.py") to exec form ("python3", ["/path/..."]), and
    an upgrade must still recognise the entry it is replacing."""
    return any(
        MARKER in h.get("command", "")
        or any(MARKER in a for a in h.get("args", []))
        for h in group.get("hooks", [])
    )


CLAUDE_EVENTS = ("PreToolUse", "PostToolUse")


def _claude_entries(command: str) -> dict[str, list[dict[str, Any]]]:
    """The registrations we write, per event. Shell form, because only a shell
    string can carry the `|| exit 0` guard (see guarded)."""
    handler = {"type": "command", "command": command, "timeout": 5}
    return {
        "PreToolUse": [
            # Real edits: recorded exactly, and they trigger the one prompt.
            {"matcher": "Write|Edit|NotebookEdit", "hooks": [handler]},
            # Shell calls: recorded as opaque. Without this, an assistant that
            # writes through `python3 - <<EOF` or `sed -i` leaves no trace and
            # the work reads as human-written.
            {"matcher": "Bash|PowerShell", "hooks": [handler]},
        ],
        # Edits: the observation that a prompted edit was approved. Shell
        # calls: the tree after the call, so what it wrote is seen, not assumed.
        "PostToolUse": [
            {"matcher": "Write|Edit|NotebookEdit", "hooks": [handler]},
            {"matcher": "Bash|PowerShell", "hooks": [handler]},
        ],
    }


def guarded(hook_path: str) -> str:
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
    return sys.executable + " " + shlex.quote(hook_path) + " || exit 0"


def _write(path: str, data: Any, empty: Any) -> None:
    """Write, or delete the file if we emptied something we alone populated."""
    if data == empty and os.path.exists(path):
        os.remove(path)
        if os.path.exists(path + ".grit-backup"):
            os.remove(path + ".grit-backup")
        print("  removed     %s (it held nothing else)" % path)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def zrb(path: str, hook: str, action: str) -> Any:
    data = _load_with_backup(path)
    if data is None:
        data = []
    if not isinstance(data, list):
        print("  %s is not a hook array — leaving it alone" % path, file=sys.stderr)
        sys.exit(3)

    data[:] = [h for h in data if h.get("name") != ZRB_HOOK_NAME]
    if action == "install":
        data.append(
            {
                "name": ZRB_HOOK_NAME,
                "description": "Record who wrote the code; offer self-completion once a session.",
                "events": ["PreToolUse", "PostToolUse"],
                "type": "command",
                "matchers": [
                    {
                        "field": "tool_name",
                        "operator": "regex",
                        "value": "^(Write|Edit|NotebookEdit|Bash|PowerShell)$",
                    }
                ],
                "config": {"command": guarded(hook), "shell": True},
                "timeout": 5,
            }
        )
    _write(path, data, empty=[])
    return data


if __name__ == "__main__":
    main()
