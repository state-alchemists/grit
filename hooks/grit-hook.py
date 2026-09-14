#!/usr/bin/env python3
"""grit — PreToolUse hook for Write/Edit.

Two jobs, in order of how much they matter:

  1. RECORD who wrote the code. Every time the assistant writes bytes, that is
     logged to <project>/.grit/authorship.jsonl. This is the only number in the
     whole product that cannot be talked out of: it is not a self-report, it is
     a count of tool calls that actually happened.

  2. ASK, ONCE. The first time the assistant reaches for the editor in a
     session, surface the choice. Once. After that this hook is silent for the
     rest of the session, because a prompt on every edit is how a tool gets
     uninstalled.

Design constraints this file must never violate:
  - It must never block editing because it broke. Any error at all: exit 0.
  - It must be fast. No network, no imports beyond the stdlib.
  - It must be trivial to switch off, and obvious how (see OFF SWITCHES).

OFF SWITCHES
  GRIT_OFF=1               environment, kills it everywhere
  touch .grit/off          per project
  "ask_on_first_edit":false in ~/.grit/preferences.json — keeps the recording,
                           drops the prompt
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

HOME_ROOT = os.path.expanduser(os.environ.get("GRIT_ROOT", "~/.grit"))

# Tools that write files directly. Line counts here are exact.
WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")

# Tools that MAY write files, via a shell, where we cannot see what changed.
# Matching these matters more than it looks: an assistant that edits through
# `python3 - <<EOF` or `sed -i` produces an empty authorship log, and anything
# reading that log then concludes the human wrote the code. Recording the call
# without a line count is not as good as observing the edit — but "something
# unattributable happened" is a true statement, and silence is a false one.
SHELL_TOOLS = ("Bash", "PowerShell")


def _lines(tool_input):
    """How many lines the assistant is about to write."""
    text = tool_input.get("content")  # Write
    if text is None:
        text = tool_input.get("new_string", "")  # Edit
    return len(str(text).splitlines())


def _prefs():
    try:
        with open(os.path.join(HOME_ROOT, "preferences.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _duplicate(event):
    """True if this exact edit already came through moments ago.

    One edit can reach this hook more than once, for reasons that are all
    legitimate: a user-level and a project-level registration both matching, or
    zrb reading `~/.claude/settings.json` on top of its own `hooks.json`. Left
    alone that double-counts authorship, which is the one number here that is
    supposed to be beyond argument.

    Keyed on the event itself and a 2-second window, so genuine repeat edits of
    the same file are still counted separately.
    """
    tool_input = event.get("tool_input") or {}
    # hashlib, not hash(): Python salts hash() per process, so two invocations
    # of this script would never agree on the same content — which is exactly
    # the case we are trying to detect.
    body = str(tool_input.get("content") or tool_input.get("new_string", ""))
    key = "%s|%s|%s|%s" % (
        event.get("session_id", ""),
        event.get("tool_name", ""),
        tool_input.get("file_path", ""),
        hashlib.sha1(body.encode("utf-8", "replace")).hexdigest(),
    )
    path = os.path.join(HOME_ROOT, ".last-event")
    now = time.time()
    try:
        prev_key, prev_at = open(path, encoding="utf-8").read().rsplit(" ", 1)
        if prev_key == key and now - float(prev_at) < 2.0:
            return True
    except Exception:
        pass
    try:
        os.makedirs(HOME_ROOT, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("%s %f" % (key, now))
    except Exception:
        pass
    return False


def _already_asked(session_id):
    """One ask per session. The marker lives with the user's own state, not the
    project, so it survives switching between repos in one session."""
    if not session_id:
        return True  # no id -> never nag
    marker_dir = os.path.join(HOME_ROOT, "asked")
    marker = os.path.join(marker_dir, str(session_id)[:64].replace("/", "_"))
    if os.path.exists(marker):
        return True
    os.makedirs(marker_dir, exist_ok=True)
    with open(marker, "w") as fh:
        fh.write(datetime.now(timezone.utc).isoformat())
    return False


def main():
    raw = sys.stdin.read()
    event = json.loads(raw or "{}")

    tool = event.get("tool_name", "")
    if tool not in WRITE_TOOLS and tool not in SHELL_TOOLS:
        return

    cwd = event.get("cwd") or os.getcwd()
    if os.environ.get("GRIT_OFF") == "1" or os.path.exists(
        os.path.join(cwd, ".grit", "off")
    ):
        return

    # One event, one record — even when two registrations both match it.
    if _duplicate(event):
        return

    tool_input = event.get("tool_input") or {}

    # ── 1. Record. Always, silently. ─────────────────────────────────────────
    try:
        grit_dir = os.path.join(cwd, ".grit")
        os.makedirs(grit_dir, exist_ok=True)
        with open(
            os.path.join(grit_dir, "authorship.jsonl"), "a", encoding="utf-8"
        ) as fh:
            row = {
                "at": datetime.now(timezone.utc).isoformat(),
                "author": "assistant",
                "tool": tool,
                "session": event.get("session_id", ""),
            }
            if tool in WRITE_TOOLS:
                row["file"] = tool_input.get("file_path", "")
                row["lines"] = _lines(tool_input)
            else:
                # A shell command. We cannot know what it touched, so we say so
                # rather than recording a zero that reads like "wrote nothing".
                row["command"] = str(tool_input.get("command", ""))[:400]
                row["opaque"] = True
            fh.write(json.dumps(row) + "\n")
        # Remember which projects have a log, so the dashboard can find them.
        # The log is per-project but the dashboard is per-person, and without
        # this pointer the only working feature stays invisible.
        reg = os.path.join(HOME_ROOT, "projects.json")
        try:
            known = json.load(open(reg, encoding="utf-8"))
        except Exception:
            known = []
        if cwd not in known:
            known.append(cwd)
            os.makedirs(HOME_ROOT, exist_ok=True)
            with open(reg, "w", encoding="utf-8") as fh:
                json.dump(known[-50:], fh, indent=2)
    except Exception:
        pass  # recording must never cost the user an edit

    # ── 2. Ask, once per session — on real edits only. ───────────────────────
    # Bash is recorded but never prompts: most shell calls are reads and builds,
    # and a prompt on each one is how this gets uninstalled.
    if tool not in WRITE_TOOLS:
        return

    prefs = _prefs()
    if prefs.get("ask_on_first_edit") is False:
        return
    if _already_asked(event.get("session_id")):
        return

    name = os.path.basename(tool_input.get("file_path", "") or "this file")

    # Record that the choice was put to them. Without this the prompt is
    # decoration: nothing downstream can tell an offer that was taken from one
    # that was never made. We cannot observe the answer directly — the runtime
    # does not report it back — but "offered at T, and no assistant edit
    # followed in this session" is a sound inference, and it is the only
    # evidence this product has that anyone ever chose to do the work.
    try:
        with open(
            os.path.join(cwd, ".grit", "authorship.jsonl"), "a", encoding="utf-8"
        ) as fh:
            fh.write(
                json.dumps(
                    {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "author": "grit",
                        "event": "offered",
                        "session": event.get("session_id", ""),
                        "file": tool_input.get("file_path", ""),
                    }
                )
                + "\n"
            )
    except Exception:
        pass

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": (
                        "grit: about to write %s for you.\n"
                        'Approve to let it. Or reject and say "I\'ll do it" — the '
                        "assistant will break the work into steps, stay out of the way, "
                        "and check your result.\n"
                        "This asks once per session. Silence it with: touch .grit/off"
                        % name
                    ),
                }
            }
        )
    )


def _log_failure(exc):
    """Exit 0 on any error — but leave a trace.

    A silent `except: pass` makes a broken hook indistinguishable from a
    working one: no output is also what success looks like. That is how a tool
    ships dead and nobody notices for a month.
    """
    try:
        os.makedirs(HOME_ROOT, exist_ok=True)
        with open(
            os.path.join(HOME_ROOT, "hook-errors.log"), "a", encoding="utf-8"
        ) as fh:
            fh.write(
                "%s  %s: %s\n"
                % (datetime.now(timezone.utc).isoformat(), type(exc).__name__, exc)
            )
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never stop someone editing a file
        _log_failure(exc)
    sys.exit(0)
