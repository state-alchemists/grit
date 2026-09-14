#!/usr/bin/env python3
"""grit verify-edit — what changed during a handover, and who can be proven to
have written it.

    python3 verify_edit.py snapshot <task-id>    # at handover, before they start
    python3 verify_edit.py verify   <task-id>    # after the acceptance check passes

WHY THIS EXISTS
The PreToolUse hook observes the assistant's edits directly, which is the only
un-arguable authorship signal there is. But the hook needs a runtime that has
PreToolUse — Claude Code and zrb do; Codex, OpenCode and Gemini do not. Without
it there is nothing watching, and the temptation is to let the assistant simply
assert "the user wrote this". That assertion is worthless: it is the self-report
this project exists to replace, just wearing a different hat.

So this script proves what it can and refuses to guess the rest:

  WHAT CHANGED    git, mechanically. Always available, never a judgment call.
  WHO WROTE IT    subtracted from the hook's authorship log, when there is one.
                  With no hook, attribution is reported as `unverified` — not
                  as `human`, and not silently dropped.

An `unverified` verdict is a real result. It says the work happened and nobody
can prove who did it, which is the truth on a runtime without a hook.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HOME_ROOT = os.path.expanduser(os.environ.get("GRIT_ROOT", "~/.grit"))


def _git(*args, cwd="."):
    """Run a git command. Returns None when git or the repo is unavailable,
    rather than raising — a project without git is a supported situation."""
    try:
        out = subprocess.run(
            ("git",) + args, cwd=cwd, capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def _state(cwd="."):
    """A content fingerprint of the working tree: HEAD plus the full diff of
    tracked changes plus the list of untracked files. Enough to tell whether
    anything moved, and to produce a real diff later."""
    head = _git("rev-parse", "HEAD", cwd=cwd)
    if head is None:
        return None
    # Exclude .grit/ everywhere. Taking a snapshot writes a file under .grit/,
    # which would otherwise show up as a working-tree change and make every
    # verify report "yes, something changed" — the tool detecting itself.
    diff = _git("diff", "HEAD", "--", ".", ":(exclude).grit", cwd=cwd) or ""
    untracked = (
        _git(
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            ".",
            ":(exclude).grit",
            cwd=cwd,
        )
        or ""
    )
    return {
        "head": head.strip(),
        "diff_sha": hashlib.sha256(diff.encode()).hexdigest()[:16],
        "untracked": sorted(untracked.split()),
        "at": datetime.now(timezone.utc).isoformat(),
    }


def _store(cwd, task):
    d = os.path.join(cwd, ".grit", "snapshots")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.json" % str(task).replace("/", "_"))


def _assistant_lines(cwd, since_iso):
    """Lines the assistant is *observed* to have written since the snapshot.

    Returns None when there is no authorship log at all — which means no hook is
    running, not that the assistant wrote nothing. The difference matters: one
    is evidence, the other is absence of evidence, and collapsing them is how a
    measurement quietly becomes a flattering guess.
    """
    path = os.path.join(cwd, ".grit", "authorship.jsonl")
    if not os.path.exists(path):
        # No log. Two very different situations, and conflating them cost the
        # first task in every fresh repository: with a hook wired up, an absent
        # log means the assistant has written nothing here — which is the DIY
        # case and should score. With no hook, nobody was watching.
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            if here not in sys.path:  # insert once; see serve.sibling()
                sys.path.insert(0, here)
            import doctor

            if doctor.is_watching(os.path.abspath(cwd)):
                return {"lines": 0, "files": [], "opaque": 0}
        except Exception:
            pass
        return None
    total, files, opaque = 0, set(), 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("at", "") < since_iso:
                continue
            if row.get("opaque"):
                # A shell call. It may or may not have written files; nothing
                # observed what it did.
                opaque += 1
                continue
            total += int(row.get("lines") or 0)
            if row.get("file"):
                files.add(row["file"])
    return {"lines": total, "files": sorted(files), "opaque": opaque}


def snapshot(task, cwd="."):
    state = _state(cwd)
    if state is None:
        print("grit: not a git repository — cannot snapshot %s" % cwd)
        print("      verify will report attribution as 'unverified'.")
        return 1
    with open(_store(cwd, task), "w", encoding="utf-8") as fh:
        json.dump({"task": task, "before": state}, fh, indent=2)
    hook = (
        "yes"
        if os.path.exists(os.path.join(cwd, ".grit", "authorship.jsonl"))
        else "no (or not yet)"
    )
    print("grit: snapshot taken for task %s" % task)
    print("  head:            %s" % state["head"][:12])
    print("  authorship log:  %s" % hook)
    return 0


def verify(task, cwd="."):
    path = _store(cwd, task)
    if not os.path.exists(path):
        print(
            "grit: no snapshot for task %s — run `snapshot %s` at handover"
            % (task, task)
        )
        return 1
    with open(path, encoding="utf-8") as fh:
        before = json.load(fh)["before"]

    after = _state(cwd)
    if after is None:
        print("grit: not a git repository — attribution unverified")
        return 1

    changed = (
        after["head"] != before["head"]
        or after["diff_sha"] != before["diff_sha"]
        or after["untracked"] != before["untracked"]
    )

    diff = (
        _git("diff", "--stat", before["head"], "--", ".", ":(exclude).grit", cwd=cwd)
        or ""
    )
    assistant = _assistant_lines(cwd, before["at"])

    print("grit: task %s" % task)
    print("  changed since handover: %s" % ("yes" if changed else "NO"))
    if diff.strip():
        for line in diff.strip().splitlines()[-6:]:
            print("    %s" % line)

    if not changed:
        print(
            "  verdict: NOTHING CHANGED — the check cannot have been earned "
            "by work done here."
        )
        return 2

    if assistant is None:
        print("  assistant edits: no authorship log — no hook on this runtime")
        print(
            "  verdict: UNVERIFIED. The work happened; who wrote it is not "
            "provable here."
        )
        print("           Record it as assisted, or install the hook:")
        print("           bin/install.sh --zrb   (or --claude)")
        return 3

    if assistant["lines"] == 0:
        if assistant["opaque"]:
            # The decisive case. Zero observed edits is NOT evidence of a human
            # author when the assistant also ran shell commands that nothing
            # watched — `python3 - <<EOF`, `sed -i` and friends all write files
            # while producing no edit event at all.
            print(
                "  assistant edits: none observed, but %d shell command(s) ran"
                % assistant["opaque"]
            )
            print(
                "  verdict: UNVERIFIED. A shell command can write files "
                "without being seen, so 'nothing observed' does not mean "
                "'the human wrote it'."
            )
            return 3
        print("  assistant edits: none observed since the snapshot")
        print("  verdict: HUMAN-WRITTEN, by observation.")
        return 0

    print(
        "  assistant edits: %d lines across %d file(s)"
        % (assistant["lines"], len(assistant["files"]))
    )
    for f in assistant["files"][:5]:
        print("    %s" % f)
    print("  verdict: ASSISTED — the assistant wrote part of this.")
    return 1


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("snapshot", "verify"):
        print(__doc__.strip().splitlines()[0])
        print("usage: verify_edit.py {snapshot|verify} <task-id> [path]")
        return 2
    cmd, task = sys.argv[1], sys.argv[2]
    cwd = sys.argv[3] if len(sys.argv) > 3 else "."
    return (snapshot if cmd == "snapshot" else verify)(task, cwd)


if __name__ == "__main__":
    sys.exit(main())
