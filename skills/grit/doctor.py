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

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

MARKER = "grit-hook.py"

# A reader pulls (label, command) pairs out of one runtime's config shape.
# Both runtimes look different on disk and identical after this.
Entry = tuple[str, str]
Reader = Callable[[str], list[Entry]]


def main() -> int:
    project = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    print("grit doctor — project: %s\n" % project)
    checks: list[RegistrationCheck] = []
    for label, path, reader in _get_hook_sites(project):
        if not os.path.exists(path):
            continue
        entries = reader(path)
        if entries:
            checks.extend(_report_site(label, path, entries))

    if not checks:
        print("No grit hook registrations found. Nothing is recording authorship.")
        print(
            "Install one with:  bin/install.sh        (or --here for this project only)"
        )
        return 1

    bad = [c for c in checks if c.status != "ok"]
    print("%d registration(s), %d with problems." % (len(checks), len(bad)))
    if bad:
        print("\nFix them all by reinstalling — it replaces its own entries in place:")
        print("  bin/install.sh")
        return 1
    print("All registrations point at a real script and cannot block a tool call.")
    return 0


def _get_hook_sites(project: str) -> list[tuple[str, str, Reader]]:
    """Every place a registration can hide, on this machine and this project."""
    home = os.path.expanduser("~")
    return [
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


def _commands_in_claude(path: str) -> list[Entry]:
    """Pull our command strings out of a Claude-shaped settings file."""
    out: list[Entry] = []
    try:
        with open(path, encoding="utf-8") as fh:
            data: Any = json.load(fh)
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


def _commands_in_zrb(path: str) -> list[Entry]:
    out: list[Entry] = []
    try:
        with open(path, encoding="utf-8") as fh:
            data: Any = json.load(fh)
    except Exception:
        return out
    if not isinstance(data, list):
        return out
    for h in data:
        cmd = (h.get("config") or {}).get("command", "")
        if MARKER in cmd or h.get("name") == "grit-authorship":
            out.append((h.get("name", "?"), cmd))
    return out


@dataclass
class RegistrationCheck:
    """One registration and everything wrong with it. `status` is the verdict a
    reader acts on: BROKEN means it can block every tool call in the project."""

    label: str
    command: str
    script: Optional[str]
    exists: bool
    guarded: bool
    will_block: bool

    @property
    def notes(self) -> list[str]:
        out: list[str] = []
        if not self.exists:
            out.append("SCRIPT MISSING: %s" % (self.script or "unparseable"))
        if not self.guarded:
            out.append(
                "no `|| exit 0` guard — a missing script would block every write"
            )
        if self.will_block:
            out.append(
                "RETURNS EXIT 2 — this registration BLOCKS every matching tool call"
            )
        return out

    @property
    def status(self) -> str:
        if not self.notes:
            return "ok"
        return "BROKEN" if (self.will_block or not self.exists) else "risky"


def _report_site(
    label: str, path: str, entries: list[Entry]
) -> list[RegistrationCheck]:
    """Print one config file's registrations. Returns what it found, so the
    caller can total them."""
    print("%s  (%s)" % (label, path))
    checks = [_inspect(key, command) for key, command in entries]
    for check in checks:
        print("  [%-6s] %s" % (check.status, check.label or "(all)"))
        print("           %s" % check.command)
        for note in check.notes:
            print("           ! %s" % note)
    print()
    return checks


def _inspect(label: str, command: str) -> RegistrationCheck:
    """Run the checks that matter for one registration."""
    script = _get_script_path(command)
    return RegistrationCheck(
        label=label,
        command=command,
        script=script,
        exists=script is not None and os.path.exists(script),
        guarded="|| exit 0" in command,
        will_block=_blocks(command),
    )


def _get_script_path(command: str) -> Optional[str]:
    """The .py path inside a command string, however it is quoted."""
    try:
        for tok in shlex.split(command):
            if tok.endswith(".py"):
                return tok
    except ValueError:
        pass
    return None


def _blocks(command: str) -> bool:
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


def is_watching(project: str) -> bool:
    """True when a grit hook is registered AND its script exists.

    The difference between "no hook" and "a hook that saw nothing" is the
    difference between UNVERIFIED and HUMAN-WRITTEN, and an absent log file
    alone cannot tell them apart — a fresh repository has no log until the
    assistant's first edit, which is precisely the case where the human did
    all the work.
    """
    for _, path, reader in _get_hook_sites(project):
        if not os.path.exists(path):
            continue
        for _, command in reader(path):
            script = _get_script_path(command)
            if script and os.path.exists(script):
                return True
    return False


if __name__ == "__main__":
    sys.exit(main())
