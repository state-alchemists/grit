#!/usr/bin/env python3
"""grit doctor — find every hook registration and check it can actually run.

Why this exists: a hook whose script is missing does not degrade quietly.
`python3 /gone.py` exits **2**, and 2 is the code both zrb and Claude Code read
as *block this tool call* — so a stale path stops every Write and Edit in that
project, reported as a confusing Python error. It is invisible until someone
reads the config by hand, and by then a work session is gone.

So: list every place a registration can hide, and say plainly which ones work.

Usage: _doctor.py [project-dir]
"""

import json
import os
import shlex
import subprocess
import sys

MARKER = "grit-hook.py"


def _commands_in_claude(path):
    """Pull our command strings out of a Claude-shaped settings file."""
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return out
    for group in (data.get("hooks") or {}).get("PreToolUse", []) or []:
        for h in group.get("hooks", []):
            cmd = h.get("command", "")
            args = h.get("args") or []
            full = " ".join([cmd] + list(args))
            if MARKER in full:
                out.append((group.get("matcher", ""), full))
    return out


def _commands_in_zrb(path):
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return out
    if not isinstance(data, list):
        return out
    for h in data:
        cmd = (h.get("config") or {}).get("command", "")
        if MARKER in cmd or h.get("name") == "grit-authorship":
            out.append((h.get("name", "?"), cmd))
    return out


def _script_of(command):
    """The .py path inside a command string, however it is quoted."""
    try:
        for tok in shlex.split(command):
            if tok.endswith(".py"):
                return tok
    except ValueError:
        pass
    return None


def _blocks(command):
    """Does this command return the block code when it cannot run?

    Run it with empty stdin and see. Exit 2 is the failure that matters; the
    guard `|| exit 0` is what makes it impossible.
    """
    try:
        p = subprocess.run(
            command, shell=True, input="{}", text=True, capture_output=True, timeout=10
        )
        return p.returncode == 2
    except Exception:
        return False


def is_watching(project):
    """True when a grit hook is registered AND its script exists.

    The difference between "no hook" and "a hook that saw nothing" is the
    difference between UNVERIFIED and HUMAN-WRITTEN, and an absent log file
    alone cannot tell them apart — a fresh repository has no log until the
    assistant's first edit, which is precisely the case where the human did
    all the work.
    """
    home = os.path.expanduser("~")
    for path, reader in (
        (os.path.join(home, ".claude", "settings.json"), _commands_in_claude),
        (os.path.join(project, ".claude", "settings.json"), _commands_in_claude),
        (os.path.join(home, ".zrb", "hooks.json"), _commands_in_zrb),
        (os.path.join(project, ".zrb", "hooks.json"), _commands_in_zrb),
    ):
        if not os.path.exists(path):
            continue
        for _, command in reader(path):
            script = _script_of(command)
            if script and os.path.exists(script):
                return True
    return False


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    home = os.path.expanduser("~")

    sites = [
        (
            "claude user",
            os.path.join(home, ".claude", "settings.json"),
            _commands_in_claude,
        ),
        (
            "claude project",
            os.path.join(project, ".claude", "settings.json"),
            _commands_in_claude,
        ),
        ("zrb user", os.path.join(home, ".zrb", "hooks.json"), _commands_in_zrb),
        ("zrb project", os.path.join(project, ".zrb", "hooks.json"), _commands_in_zrb),
    ]

    print("grit doctor — project: %s\n" % project)
    found = bad = 0
    for label, path, reader in sites:
        if not os.path.exists(path):
            continue
        entries = reader(path)
        if not entries:
            continue
        print("%s  (%s)" % (label, path))
        for key, command in entries:
            found += 1
            script = _script_of(command)
            exists = bool(script) and os.path.exists(script)
            guarded = "|| exit 0" in command
            will_block = _blocks(command)
            status = "ok"
            notes = []
            if not exists:
                notes.append("SCRIPT MISSING: %s" % (script or "unparseable"))
            if not guarded:
                notes.append(
                    "no `|| exit 0` guard — a missing script would block every write"
                )
            if will_block:
                notes.append(
                    "RETURNS EXIT 2 — this registration BLOCKS every matching tool call"
                )
            if notes:
                status = "BROKEN" if (will_block or not exists) else "risky"
                bad += 1
            print("  [%-6s] %s" % (status, key or "(all)"))
            print("           %s" % command)
            for n in notes:
                print("           ! %s" % n)
        print()

    if found == 0:
        print("No grit hook registrations found. Nothing is recording authorship.")
        print(
            "Install one with:  bin/install.sh        (or --here for this project only)"
        )
        return 1

    print("%d registration(s), %d with problems." % (found, bad))
    if bad:
        print("\nFix them all by reinstalling — it replaces its own entries in place:")
        print("  bin/install.sh")
        return 1
    print("All registrations point at a real script and cannot block a tool call.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
