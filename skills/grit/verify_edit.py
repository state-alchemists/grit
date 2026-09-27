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

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

HOME_ROOT = os.path.expanduser(os.environ.get("GRIT_ROOT", "~/.grit"))

# The four verdicts this tool can reach. `UNVERIFIED` is deliberately distinct
# from `HUMAN-WRITTEN`: an AGENTS.md rule says never upgrade one to the other.
Verdict = Literal[
    "HUMAN-WRITTEN",
    "ASSISTED",
    "UNVERIFIED",
    "NOTHING CHANGED",
]
# Exit codes double as the machine-readable verdict, so a caller can branch
# without parsing prose.
EXIT_UNCHANGED = 2
EXIT_UNVERIFIED = 3
# A failure to run is not a verdict, and must never share a code with one.
# Every error path used to return 1 or 2 — ASSISTED and NOTHING CHANGED — so a
# mistyped task id read as a real result: the caller either recorded
# `assistance: full` against work the user did alone, or recorded nothing at
# all and lost it. Errors take a code no verdict can (EX_USAGE, sysexits.h).
EXIT_ERROR = 64


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in ("snapshot", "verify"):
        print(__doc__.strip().splitlines()[0])
        print("usage: verify_edit.py {snapshot|verify} <task-id> [path]")
        return EXIT_ERROR
    cmd, task = sys.argv[1], sys.argv[2]
    cwd = sys.argv[3] if len(sys.argv) > 3 else "."
    return (snapshot if cmd == "snapshot" else verify)(task, cwd)


@dataclass(frozen=True)
class TreeState:
    """A content fingerprint of the working tree: HEAD plus the full diff of
    tracked changes plus the list of untracked files. Enough to tell whether
    anything moved, and to produce a real diff later."""

    head: str
    diff_sha: str
    untracked: tuple[str, ...]
    at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "head": self.head,
            "diff_sha": self.diff_sha,
            "untracked": list(self.untracked),
            "at": self.at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TreeState":
        return cls(
            head=str(raw.get("head", "")),
            diff_sha=str(raw.get("diff_sha", "")),
            untracked=tuple(raw.get("untracked", [])),
            at=str(raw.get("at", "")),
        )

    def differs_from(self, other: "TreeState") -> bool:
        return (
            self.head != other.head
            or self.diff_sha != other.diff_sha
            or self.untracked != other.untracked
        )


@dataclass(frozen=True)
class Attribution:
    """What the authorship log says the assistant wrote.

    `None` (the absence of this object) is a distinct result from a zero-line
    Attribution: one is "nobody was watching", the other is "the watcher saw
    nothing". Collapsing them is how a measurement becomes a flattering guess.
    """

    lines: int
    files: tuple[str, ...] = field(default_factory=tuple)
    opaque: int = 0  # shell calls nothing observed the effect of
    shell_files: tuple[str, ...] = field(default_factory=tuple)  # written by shell calls

    def to_dict(self) -> dict[str, Any]:
        return {
            "lines": self.lines,
            "files": list(self.files),
            "opaque": self.opaque,
            "shell_files": list(self.shell_files),
        }


def snapshot(task: str, cwd: str = ".") -> int:
    state = _get_tree_state(cwd)
    if state is None:
        print("grit: not a git repository — cannot snapshot %s" % cwd)
        print("      verify will report attribution as 'unverified'.")
        return EXIT_ERROR
    with open(_get_snapshot_path(cwd, task), "w", encoding="utf-8") as fh:
        json.dump({"task": task, "before": state.to_dict()}, fh, indent=2)
    hook = (
        "yes"
        if os.path.exists(
            os.path.join(get_project_dir(HOME_ROOT, cwd), "authorship.jsonl")
        )
        else "no (or not yet)"
    )
    print("grit: snapshot taken for task %s" % task)
    print("  head:            %s" % state.head[:12])
    print("  authorship log:  %s" % hook)
    return 0


def verify(task: str, cwd: str = ".") -> int:
    """Report what changed and who can be proven to have written it."""
    before = _load_snapshot(task, cwd)
    if before is None:
        return EXIT_ERROR
    after = _get_tree_state(cwd)
    if after is None:
        # The message and bin/install.sh have always called this UNVERIFIED;
        # only the exit code said ASSISTED. Credit is unchanged either way —
        # both score as `full` — but the caller now reads what it is told.
        print("grit: not a git repository — attribution unverified")
        _record_task(cwd, task, EXIT_UNVERIFIED, None, None)
        return EXIT_UNVERIFIED

    changed = after.differs_from(before)
    assistant = _get_assistant_lines(cwd, before.at)
    _report_handover(task, before, cwd, changed)
    code = _decide_verdict(changed, assistant)
    _record_task(cwd, task, code, _count_changed_lines(before, after, cwd), assistant)
    return code


VERDICT_BY_EXIT: dict[int, Verdict] = {
    0: "HUMAN-WRITTEN",
    1: "ASSISTED",
    EXIT_UNCHANGED: "NOTHING CHANGED",
    EXIT_UNVERIFIED: "UNVERIFIED",
}


def _record_task(
    cwd: str,
    task: str,
    code: int,
    changed: Optional[dict[str, int]],
    assistant: Optional[Attribution],
) -> None:
    """Append this verdict to the project's tasks.jsonl — the dashboard's
    per-task record of who did the work. Append-only: a re-verify adds a row
    and the reader shows the latest, so no verdict is ever rewritten.

    Written from here, not by the assistant, so the record is whatever the
    tool actually decided. Never fails the verdict: the exit code is the answer.
    """
    row: dict[str, Any] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "verdict": VERDICT_BY_EXIT[code],
        **(changed or {}),
    }
    if assistant is not None:
        row.update(
            assistant_lines=assistant.lines,
            assistant_files=len(assistant.files),
            shell_calls=assistant.opaque,
            shell_files=len(assistant.shell_files),
        )
    try:
        path = os.path.join(get_project_dir(HOME_ROOT, cwd), "tasks.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


def _count_changed_lines(
    before: TreeState, after: TreeState, cwd: str
) -> dict[str, int]:
    """Lines added and removed since the snapshot, from git: tracked changes
    against the snapshot's HEAD, plus every line of a file that was untracked
    and new since then (git diff cannot see those)."""
    added = removed = 0
    files: set[str] = set()
    for line in (_git("diff", "--numstat", before.head, "--", ".", cwd=cwd) or "").splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            added, removed = added + int(parts[0]), removed + int(parts[1])
            files.add(parts[2])
    for name in set(after.untracked) - set(before.untracked):
        try:
            with open(os.path.join(cwd, name), encoding="utf-8", errors="replace") as fh:
                added += sum(1 for _ in fh)
            files.add(name)
        except OSError:
            continue
    return {"files_changed": len(files), "lines_added": added, "lines_removed": removed}


def _get_tree_state(cwd: str = ".") -> Optional[TreeState]:
    head = _git("rev-parse", "HEAD", cwd=cwd)
    if head is None:
        return None
    diff = _git("diff", "HEAD", "--", ".", cwd=cwd) or ""
    untracked = (
        _git(
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            ".",
            cwd=cwd,
        )
        or ""
    )
    return TreeState(
        head=head.strip(),
        diff_sha=hashlib.sha256(diff.encode()).hexdigest()[:16],
        untracked=tuple(sorted(untracked.splitlines())),
        at=datetime.now(timezone.utc).isoformat(),
    )


def _load_snapshot(task: str, cwd: str) -> Optional[TreeState]:
    path = _get_snapshot_path(cwd, task)
    if not os.path.exists(path):
        print(
            "grit: no snapshot for task %s — run `snapshot %s` at handover"
            % (task, task)
        )
        return None
    with open(path, encoding="utf-8") as fh:
        return TreeState.from_dict(json.load(fh)["before"])


def _get_snapshot_path(cwd: str, task: str) -> str:
    d = os.path.join(get_project_dir(HOME_ROOT, cwd), "snapshots")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.json" % str(task).replace("/", "_"))


def _get_assistant_lines(cwd: str, since_iso: str) -> Optional[Attribution]:
    """Lines the assistant is *observed* to have written since the snapshot.

    Returns None when there is no authorship log at all — which means no hook is
    running, not that the assistant wrote nothing. The difference matters: one
    is evidence, the other is absence of evidence, and collapsing them is how a
    measurement quietly becomes a flattering guess.
    """
    path = os.path.join(get_project_dir(HOME_ROOT, cwd), "authorship.jsonl")
    if not os.path.exists(path):
        return _attribution_without_a_log(cwd)
    return _read_authorship_log(path, since_iso)


def _read_authorship_log(path: str, since_iso: str) -> Attribution:
    total = 0
    files: set[str] = set()
    shell_calls: list[tuple[str, str]] = []  # (tool_use_id or "", command)
    results: dict[str, list[str]] = {}  # tool_use_id -> paths it wrote
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("event") == "shell-result":
                results[str(row.get("tool_use_id"))] = list(row.get("written") or [])
                continue
            if row.get("at", "") < since_iso or row.get("author") != "assistant":
                continue
            if row.get("opaque"):
                shell_calls.append((str(row.get("tool_use_id") or ""), str(row.get("command", ""))))
                continue
            total += int(row.get("lines") or 0)
            if row.get("file"):
                files.add(row["file"])
    # A shell call counts as unobserved unless the hook saw its result: one
    # that wrote nothing is harmless (running the user's tests, running this
    # script), one that wrote files wrote them for the user.
    if shell_calls and shell_calls[-1][0] not in results and _is_this_verify(shell_calls[-1][1]):
        shell_calls.pop()  # the call running this script: its result cannot exist yet
    opaque = sum(1 for call, _ in shell_calls if call not in results)
    shell_files = sorted({p for call, _ in shell_calls for p in results.get(call, [])})
    return Attribution(
        lines=total,
        files=tuple(sorted(files)),
        opaque=opaque,
        shell_files=tuple(shell_files),
    )


_PLAIN = re.compile(r"^[\w./~:=@+-]+$")


def _is_this_verify(command: str) -> bool:
    """Is this shell command nothing but an invocation of `verify_edit.py
    verify`? Only then may it be excused for having no result yet.

    Strict on purpose: `$(...)`, backticks, `;`, pipes or redirects could run a
    write BEFORE this script reads the log, so any of them disqualifies. A
    leading `cd <dir> &&` is allowed, since it writes nothing."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) > 3 and tokens[0] == "cd" and tokens[2] == "&&":
        tokens = tokens[3:]
    if not tokens or not all(_PLAIN.match(t) for t in tokens):
        return False
    script = 1 if os.path.basename(tokens[0]).startswith("python") else 0
    return (
        len(tokens) > script + 1
        and os.path.basename(tokens[script]) == "verify_edit.py"
        and tokens[script + 1] == "verify"
    )


def _attribution_without_a_log(cwd: str) -> Optional[Attribution]:
    """No log. Two very different situations, and conflating them cost the
    first task in every fresh repository: with a hook wired up, an absent log
    means the assistant has written nothing here — which is the DIY case and
    should score. With no hook, nobody was watching.
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:  # insert once; see serve._import_sibling()
            sys.path.insert(0, here)
        import doctor

        if doctor.is_watching(os.path.abspath(cwd)):
            return Attribution(lines=0, files=(), opaque=0)
    except Exception:
        pass
    return None


def _report_handover(
    task: str, before: TreeState, cwd: str, changed: bool
) -> None:
    """Print the header and the diff stat — what happened, before the verdict."""
    diff = _git("diff", "--stat", before.head, "--", ".", cwd=cwd) or ""
    print("grit: task %s" % task)
    print("  changed since handover: %s" % ("yes" if changed else "NO"))
    if diff.strip():
        for line in diff.strip().splitlines()[-6:]:
            print("    %s" % line)


def _decide_verdict(changed: bool, assistant: Optional[Attribution]) -> int:
    """The outcome, in the order that matters: nothing changed, then nobody
    watching, then what the watcher saw."""
    if not changed:
        print(
            "  verdict: NOTHING CHANGED — the check cannot have been earned "
            "by work done here."
        )
        return EXIT_UNCHANGED
    if assistant is None:
        return _report_unverified()
    if assistant.lines == 0 and not assistant.shell_files:
        return _report_no_observed_edits(assistant)
    return _report_assisted(assistant)


def _report_unverified() -> int:
    print("  assistant edits: no authorship log — no hook on this runtime")
    print(
        "  verdict: UNVERIFIED. The work happened; who wrote it is not "
        "provable here."
    )
    print("           Record it as assisted, or install the hook:")
    print("           bin/install.sh --zrb   (or --claude)")
    return EXIT_UNVERIFIED


def _report_no_observed_edits(assistant: Attribution) -> int:
    """Zero observed edits, and whether that is evidence of anything.

    The decisive case: zero observed edits is NOT evidence of a human author
    when the assistant also ran shell commands that nothing watched —
    `python3 - <<EOF`, `sed -i` and friends all write files while producing no
    edit event at all.
    """
    if assistant.opaque:
        print(
            "  assistant edits: none observed, but %d shell command(s) ran"
            % assistant.opaque
        )
        print("           (their effect was not observed — is the PostToolUse hook installed?)")
        print(
            "  verdict: UNVERIFIED. A shell command can write files "
            "without being seen, so 'nothing observed' does not mean "
            "'the human wrote it'."
        )
        return EXIT_UNVERIFIED
    print("  assistant edits: none observed since the snapshot")
    print("  verdict: HUMAN-WRITTEN, by observation.")
    return 0


def _report_assisted(assistant: Attribution) -> int:
    print(
        "  assistant edits: %d lines across %d file(s)"
        % (assistant.lines, len(assistant.files))
    )
    for f in assistant.files[:5]:
        print("    %s" % f)
    if assistant.shell_files:
        print("  shell commands the assistant ran wrote %d file(s):" % len(assistant.shell_files))
        for f in assistant.shell_files[:5]:
            print("    %s" % f)
        print("  (a build artifact counts too — add it to .gitignore if it is not your work)")
    print("  verdict: ASSISTED — the assistant wrote part of this.")
    return 1


def _git(*args: str, cwd: str = ".") -> Optional[str]:
    """Run a git command. Returns None when git or the repo is unavailable,
    rather than raising — a project without git is a supported situation."""
    try:
        out = subprocess.run(
            ("git",) + args, cwd=cwd, capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def get_project_dir(root: str, cwd: str) -> str:
    """Where this project's own state lives under `root` (normally HOME_ROOT).

    The skill's one copy — serve.py imports it. hooks/grit-hook.py keeps its
    own because it is installed apart from the skill; test_hook.py pins that
    the two agree, since a drift sends every row to a directory nobody reads."""
    key = hashlib.sha256(os.path.realpath(cwd).encode()).hexdigest()[:16]
    return os.path.join(root, "projects", key)


if __name__ == "__main__":
    sys.exit(main())
