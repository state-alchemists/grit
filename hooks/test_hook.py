#!/usr/bin/env python3
"""Self-check for the hook. Run: python3 hooks/test_hook.py

The hook exits 0 no matter what, so "it ran" proves nothing — these assert on
what it actually did. The JSON is built with json.dumps, never with a shell
echo: an earlier version of this test used `echo` and the shell turned "\\n"
into real newlines, producing invalid JSON that the hook swallowed silently.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import subprocess as sp
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Optional
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grit-hook.py")

_hook_mod = None


def hook_module():
    """Load grit-hook.py once, so tests can reuse its own `_get_project_dir` rather
    than re-deriving the hash scheme a second time."""
    global _hook_mod
    if _hook_mod is None:
        spec = importlib.util.spec_from_file_location("grit_hook", HOOK)
        _hook_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_hook_mod)
    return _hook_mod


def get_project_dir(root: str, cwd: str) -> str:
    return hook_module()._get_project_dir(root, cwd)


def rows(
    root: str, proj: str, author: Optional[str] = "assistant"
) -> list[dict[str, Any]]:
    """Authorship rows only. The log also carries `offered` events now, and a
    count that includes them reads an offer as an edit."""
    path = os.path.join(get_project_dir(root, proj), "authorship.jsonl")
    out: list[dict[str, Any]] = []
    with open(path) as fh:
        for line in fh:
            r = json.loads(line)
            if author is None or r.get("author") == author:
                out.append(r)
    return out


def run(
    event: dict[str, Any], root: str, env: Optional[dict[str, str]] = None
) -> str:
    e = dict(os.environ, GRIT_ROOT=root)
    e.update(env or {})
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=e,
    )
    assert p.returncode == 0, "hook must always exit 0, got %d" % p.returncode
    return p.stdout.strip()


@dataclass
class HookFixture:
    """A scratch GRIT_ROOT and a scratch project, so no test touches the user's
    real state."""

    root: str
    proj: str

    def event(self, tool: str = "Write", session: str = "s1", **tool_input: Any) -> dict[str, Any]:
        return {
            "tool_name": tool,
            "session_id": session,
            "cwd": self.proj,
            "tool_input": tool_input,
        }

    def write_event(self, name: str = "a.py", content: str = "one\ntwo\nthree\n", **kw: Any) -> dict[str, Any]:
        return self.event(
            file_path=os.path.join(self.proj, name), content=content, **kw
        )

    def run(self, event: dict[str, Any], env: Optional[dict[str, str]] = None) -> str:
        return run(event, self.root, env)

    def rows(self, author: Optional[str] = "assistant") -> list[dict[str, Any]]:
        return rows(self.root, self.proj, author)

    def count_rows(self) -> int:
        return len(self.rows())


def _properties():
    """Every property, in order. A list rather than 16 bare calls so the report
    cannot disagree with what ran.

    It previously could: the printed count said 16 while only 14 were called,
    and `bin/check_docs.py` reads that number to verify the docs. A hardcoded
    figure that happens to match is a claim waiting to drift — and this one had
    already drifted once.
    """
    return [
        _property_asks_once_per_session,
        _property_records_every_edit,
        _property_edit_uses_new_string,
        _property_ignores_read_tools,
        _property_off_switches_work,
        _property_off_switch_cli,
        _property_legacy_off_marker_still_silences,
        _property_hook_log_is_read_by_daemon_and_verify,
        _property_ask_can_be_disabled,
        _property_duplicate_event_counted_once,
        _property_identical_retry_is_not_swallowed,
        _property_ask_markers_stay_bounded,
        _property_garbage_input_is_safe_and_traced,
        _property_verify_edit_distinguishes_outcomes,
        _property_error_exits_are_not_verdicts,
        _property_shell_call_forces_unverified,
        _property_bash_is_opaque_and_silent,
        _property_missing_script_cannot_block,
        _property_offer_is_recorded_distinctly,
        _property_fresh_repo_with_hook_scores,
        _property_declined_offer_counts_as_taken,
        _property_post_tool_use_confirms_without_counting,
        _property_verdicts_are_recorded_per_task,
        _property_installer_registers_and_removes_both_events,
        _property_distinct_shell_calls_are_not_merged,
        _property_observed_shell_calls_do_not_void_the_task,
    ]


def main() -> None:
    fx = HookFixture(
        root=tempfile.mkdtemp(prefix="grit-hookroot-"),
        proj=tempfile.mkdtemp(prefix="grit-proj-"),
    )
    try:
        properties = _properties()
        for check in properties:
            check(fx)
        print("ok — %d properties hold" % len(properties))
    finally:
        shutil.rmtree(fx.root, ignore_errors=True)
        shutil.rmtree(fx.proj, ignore_errors=True)


def _property_asks_once_per_session(fx: HookFixture) -> None:
    # First edit of a session asks, once.
    out = fx.run(fx.write_event())
    assert out, "first write should produce an ask"
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "ask", decision
    assert "I'll do it" in decision["permissionDecisionReason"]

    # Second edit in the same session is silent. A prompt on every edit is how
    # a tool gets uninstalled.
    assert (
        fx.run(fx.write_event("b.py", content="x\n")) == ""
    ), "hook asked twice in one session"

    # A new session asks again.
    assert fx.run(fx.write_event(session="s2")), "new session should ask"


def _property_records_every_edit(fx: HookFixture) -> None:
    # ...but it still records. Authorship is the number that matters. Counted
    # relative to where we started, so this property does not depend on how
    # many edits an earlier property happened to make.
    before = fx.count_rows()
    fx.run(fx.write_event("rec-1.py", content="one\ntwo\nthree\n", session="rec"))
    fx.run(fx.write_event("rec-2.py", content="x\n", session="rec"))
    seen = fx.rows()[before:]
    assert len(seen) == 2, "expected 2 authorship rows, got %d" % len(seen)
    assert seen[0]["lines"] == 3 and seen[0]["author"] == "assistant"
    assert seen[1]["lines"] == 1


def _property_edit_uses_new_string(fx: HookFixture) -> None:
    # Edit uses new_string, not content.
    fx.run(fx.event("Edit", session="s3", file_path=fx.proj + "/c.py", new_string="p\nq\n"))
    seen = fx.rows()
    assert seen[-1]["lines"] == 2, "Edit line count wrong: %s" % seen[-1]


def _property_ignores_read_tools(fx: HookFixture) -> None:
    # Tools that do not write code are ignored entirely.
    before = fx.count_rows()
    fx.run(fx.event("Read", session="s4", file_path=fx.proj + "/a.py"))
    assert fx.count_rows() == before, "Read should not be recorded"


def _property_off_switches_work(fx: HookFixture) -> None:
    # Both off switches actually stop it.
    assert (
        fx.run(fx.write_event(session="s5"), {"GRIT_OFF": "1"}) == ""
    ), "GRIT_OFF did not silence the hook"
    pdir = get_project_dir(fx.root, fx.proj)
    os.makedirs(pdir, exist_ok=True)
    open(os.path.join(pdir, "off"), "w").close()
    assert (
        fx.run(fx.write_event(session="s6")) == ""
    ), "the per-project off marker did not silence the hook"
    os.remove(os.path.join(pdir, "off"))


def _property_off_switch_cli(fx: HookFixture) -> None:
    # `grit-hook.py --off`/`--on` toggle the same marker `_is_switched_off` reads,
    # without the caller needing to know its hashed path.
    env = dict(os.environ, GRIT_ROOT=fx.root)
    marker = os.path.join(get_project_dir(fx.root, fx.proj), "off")

    sp.run(
        [sys.executable, HOOK, "--off", fx.proj], env=env, capture_output=True, check=True
    )
    assert os.path.exists(marker), "--off did not create the marker"
    assert fx.run(fx.write_event(session="cli-off")) == "", "--off did not silence the hook"

    sp.run(
        [sys.executable, HOOK, "--on", fx.proj], env=env, capture_output=True, check=True
    )
    assert not os.path.exists(marker), "--on did not remove the marker"


def _property_legacy_off_marker_still_silences(fx: HookFixture) -> None:
    # A `touch .grit/off` written before the project-folder restructure still
    # silences the hook. Dropping it would silently re-enable recording on an
    # upgraded machine whose user had deliberately switched the project off, and
    # silence is the one failure mode this product cannot let happen silently.
    legacy = os.path.join(fx.proj, ".grit", "off")
    os.makedirs(os.path.dirname(legacy), exist_ok=True)
    open(legacy, "w").close()
    try:
        assert (
            fx.run(fx.write_event(session="legacy-off")) == ""
        ), "a legacy .grit/off marker did not silence the hook"
    finally:
        os.remove(legacy)

    # And `grit-hook.py --on` removes the legacy marker too, so a user silenced
    # before the restructure can reliably turn the recording back on.
    env = dict(os.environ, GRIT_ROOT=fx.root)
    os.makedirs(os.path.join(fx.proj, ".grit"), exist_ok=True)
    open(legacy, "w").close()
    sp.run(
        [sys.executable, HOOK, "--on", fx.proj], env=env, capture_output=True, check=True
    )
    assert not os.path.exists(legacy), "--on did not clear the legacy marker"


def _property_hook_log_is_read_by_daemon_and_verify(fx: HookFixture) -> None:
    # One project key, derived independently in three tools — the hook writes
    # `projects/<key>/authorship.jsonl`, the daemon aggregates it, and
    # verify_edit clears a handover against it. If the derivations drift, the
    # hook writes to a directory the other two never look in: the dashboard
    # shows nothing and no task verifies, with no error anywhere. Nothing
    # pinned that until this test, which runs the real hook and then asks both
    # readers to find the log it actually wrote.
    repo = tempfile.mkdtemp(prefix="grit-chain-")
    root = tempfile.mkdtemp(prefix="grit-chain-root-")
    try:
        _init_repo(repo)
        run(
            {
                "tool_name": "Write",
                "session_id": "chain",
                "cwd": repo,
                "tool_input": {
                    "file_path": os.path.join(repo, "b.py"),
                    "content": "w=2\n",
                },
            },
            root,
        )
        log = os.path.join(get_project_dir(root, repo), "authorship.jsonl")
        assert os.path.exists(log), "the hook did not write under the shared key"

        skill = os.path.join(os.path.dirname(os.path.dirname(HOOK)), "skills", "grit")
        sys.path.insert(0, skill)
        import serve

        projects = serve.State(root).authorship()["projects"]
        assert [p["project"] for p in projects] == [os.path.realpath(repo)], (
            "the daemon did not find the log the hook wrote: %r" % projects
        )

        _verify_edit_cmd(repo, "snapshot", "chain", root=root)
        open(os.path.join(repo, "a.py"), "a").write("q=9\n")
        assert (
            _verify_edit_cmd(repo, "verify", "chain", root=root) == 0
        ), "verify_edit did not see the log the hook wrote"
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


def _property_ask_can_be_disabled(fx: HookFixture) -> None:
    # ask_on_first_edit:false keeps recording, drops the prompt.
    with open(os.path.join(fx.root, "preferences.json"), "w") as fh:
        json.dump({"ask_on_first_edit": False}, fh)
    n = fx.count_rows()
    assert (
        fx.run(fx.write_event(session="s7")) == ""
    ), "ask_on_first_edit:false should suppress the prompt"
    assert (
        fx.count_rows() == n + 1
    ), "recording must continue when only the prompt is disabled"


def _property_duplicate_event_counted_once(fx: HookFixture) -> None:
    # The same edit arriving twice is counted once. Two registrations matching
    # one event is normal (user + project level, or zrb reading Claude's
    # settings.json on top of its own hooks.json) — and would otherwise inflate
    # the one number that must not be inflatable.
    dup = {
        "tool_name": "Write",
        "session_id": "s8",
        "cwd": fx.proj,
        "tool_input": {"file_path": fx.proj + "/dup.py", "content": "k\n"},
    }
    n = fx.count_rows()
    fx.run(dup)
    fx.run(dup)
    assert fx.count_rows() == n + 1, "a doubly-registered hook double-counted one edit"


def _property_identical_retry_is_not_swallowed(fx: HookFixture) -> None:
    # Dedupe must not eat a REAL second write. Two registrations deliver one
    # event within milliseconds; a genuine retry (write, lint fails, write the
    # same content again) takes a model round-trip. The window has to sit in the
    # gap between those two, or the hook under-counts assistant authorship —
    # erring in the user's favour, which is the same defect as an editable
    # record. This was 2s, wide enough to swallow the retry.
    import time

    event = {
        "tool_name": "Write",
        "session_id": "retry",
        "cwd": fx.proj,
        "tool_input": {"file_path": fx.proj + "/retry.py", "content": "identical\n"},
    }
    n = fx.count_rows()
    fx.run(event)
    time.sleep(0.35)  # well past the dedupe window, far below a round-trip
    fx.run(event)
    assert (
        fx.count_rows() == n + 2
    ), "an identical write 350ms later was swallowed as a duplicate"


def _property_ask_markers_stay_bounded(fx: HookFixture) -> None:
    # One marker per session, and nothing else in the codebase deletes them, so
    # `~/.grit/asked/` grew for the life of the machine. Pruning is oldest-first
    # because a session that has ended is never asked about again.
    #
    # Reads the bound from the hook rather than restating it: a test that hard
    # codes 200 cannot notice the constant being raised.
    hook_mod = hook_module()

    ask_dir = os.path.join(fx.root, "asked")
    assert os.path.isdir(ask_dir), "no marker directory was ever created"
    assert len(os.listdir(ask_dir)) <= hook_mod.ASK_MARKERS_KEPT, (
        "~/.grit/asked/ grew past its bound (%d): %d"
        % (hook_mod.ASK_MARKERS_KEPT, len(os.listdir(ask_dir)))
    )


def _property_garbage_input_is_safe_and_traced(fx: HookFixture) -> None:
    # Garbage in never costs the user an edit — and is not silent.
    p = subprocess.run(
        [sys.executable, HOOK],
        input="not json at all",
        capture_output=True,
        text=True,
        env=dict(os.environ, GRIT_ROOT=fx.root),
    )
    assert p.returncode == 0, "malformed input must still exit 0"
    assert os.path.exists(
        os.path.join(fx.root, "hook-errors.log")
    ), "a swallowed failure must leave a trace"


def _verify_edit_cmd(repo: str, *args: str, root: Optional[str] = None) -> int:
    """Run verify_edit against `repo` and return its exit code, which is also
    its machine-readable verdict. `root` stands in for ~/.grit (GRIT_ROOT) —
    pass the same one used to run the hook against this repo, so both agree on
    where the project's state lives."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(HOOK)), "skills", "grit", "verify_edit.py"
    )
    env = dict(os.environ, GRIT_ROOT=root) if root else os.environ
    return sp.run(
        [sys.executable, path, *args, repo],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    ).returncode


def _property_verify_edit_distinguishes_outcomes(fx: HookFixture) -> None:
    # verify_edit distinguishes the four outcomes, and never upgrades
    # "nobody was watching" into "the human wrote it".
    repo = tempfile.mkdtemp(prefix="grit-git-")
    root = tempfile.mkdtemp(prefix="grit-git-root-")
    try:
        _init_repo(repo)
        ve = lambda *a: _verify_edit_cmd(repo, *a, root=root)

        ve("snapshot", "t1")
        assert ve("verify", "t1") == 2, "no change must not read as earned"

        open(os.path.join(repo, "a.py"), "a").write("y=2\n")
        # With NO hook registered anywhere this is UNVERIFIED; with one
        # registered it is HUMAN-WRITTEN, because a watching hook that
        # recorded nothing is evidence the assistant wrote nothing. The
        # test machine may be either, so ask before asserting.
        sys.path.insert(
            0,
            os.path.join(os.path.dirname(os.path.dirname(HOOK)), "skills", "grit"),
        )
        import doctor

        assert ve("verify", "t1") == (
            0 if doctor.is_watching(repo) else 3
        ), "verdict must follow whether a hook is actually watching"

        pdir = get_project_dir(root, repo)
        os.makedirs(pdir, exist_ok=True)
        open(os.path.join(pdir, "authorship.jsonl"), "w").close()
        ve("snapshot", "t2")
        open(os.path.join(repo, "a.py"), "a").write("z=3\n")
        assert ve("verify", "t2") == 0, "human edit with a live log = earned"
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


def _property_error_exits_are_not_verdicts(fx: HookFixture) -> None:
    # A failure to run must not share an exit code with a verdict. Every error
    # path used to return 1 (ASSISTED) or 2 (NOTHING CHANGED), and SKILL.md
    # tells the assistant to branch on exactly those numbers — so a mistyped
    # task id scored the user's unaided work as `assistance: full`, and a bad
    # subcommand threw a real task away as "the check was already green".
    verdicts = {0, 1, 2, 3}
    repo = tempfile.mkdtemp(prefix="grit-exit-")
    try:
        _init_repo(repo)
        assert _verify_edit_cmd(repo, "verify", "never-snapshotted") not in verdicts, (
            "a missing snapshot must not read as a verdict"
        )
        assert _verify_edit_cmd(repo, "notacommand", "t") not in verdicts, (
            "an unknown subcommand must not read as a verdict"
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    # Outside git there is nothing to snapshot, so snapshot is an error — but
    # `verify` against a stale snapshot is UNVERIFIED, which is what the
    # message and bin/install.sh have always said it was.
    plain = tempfile.mkdtemp(prefix="grit-nogit-")
    try:
        assert _verify_edit_cmd(plain, "snapshot", "t") not in verdicts, (
            "snapshot outside git must not read as a verdict"
        )
    finally:
        shutil.rmtree(plain, ignore_errors=True)


def _property_shell_call_forces_unverified(fx: HookFixture) -> None:
    # An unobserved shell call in the snapshot window must knock the verdict
    # back to UNVERIFIED. "No edits observed" is not proof of a human author
    # when the assistant also ran a shell.
    repo = tempfile.mkdtemp(prefix="grit-shell-")
    try:
        _init_repo(repo)
        pdir = get_project_dir(fx.root, repo)
        os.makedirs(pdir, exist_ok=True)
        open(os.path.join(pdir, "authorship.jsonl"), "w").close()
        _verify_edit_cmd(repo, "snapshot", "t3", root=fx.root)
        fx.run(
            {
                "tool_name": "Bash",
                "session_id": "z",
                "cwd": repo,
                "tool_input": {"command": "sed -i s/x/y/ a.py"},
            }
        )
        open(os.path.join(repo, "a.py"), "a").write("w=4\n")
        assert _verify_edit_cmd(repo, "verify", "t3", root=fx.root) == 3, (
            "a shell call in the window must force UNVERIFIED"
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def _init_repo(repo: str) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        sp.run(cmd, cwd=repo, capture_output=True)
    open(os.path.join(repo, "a.py"), "w").write("x=1\n")
    sp.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    sp.run(["git", "commit", "-qm", "i"], cwd=repo, capture_output=True)


def _property_bash_is_opaque_and_silent(fx: HookFixture) -> None:
    # A Bash call is recorded as opaque, never as "wrote nothing", and never
    # prompts. This is the blind spot that made an assistant editing via
    # `python3 - <<EOF` look like a human author.
    bash = {
        "tool_name": "Bash",
        "session_id": "s9",
        "cwd": fx.proj,
        "tool_input": {"command": "sed -i s/a/b/ x.py"},
    }
    n = sum(
        1
        for line in open(
            os.path.join(get_project_dir(fx.root, fx.proj), "authorship.jsonl")
        )
        if json.loads(line).get("author") == "assistant"
    )
    assert fx.run(bash) == "", "Bash must never trigger the prompt"
    seen = fx.rows()
    assert len(seen) == n + 1, "Bash call was not recorded at all"
    assert seen[-1]["opaque"] is True and "lines" not in seen[-1], (
        "a shell call must be opaque, not a zero line count: %s" % seen[-1]
    )


def _property_missing_script_cannot_block(fx: HookFixture) -> None:
    # A registration whose script is GONE must not block the tool call. Python
    # exits 2 when it cannot open a file, and 2 is exactly the code both zrb and
    # Claude Code read as "block this tool call" — so an unguarded registration
    # with a stale path silently kills every Write and Edit in the project.
    # This shipped, and cost a session.
    import shlex as _shlex

    missing = "python3 " + _shlex.quote(fx.root + "/gone.py")
    raw = sp.run(missing, shell=True, input="{}", text=True, capture_output=True)
    assert raw.returncode == 2, (
        "precondition: a missing script should exit 2 (got %d)" % raw.returncode
    )
    guarded_proc = sp.run(
        missing + " || exit 0", shell=True, input="{}", text=True, capture_output=True
    )
    assert (
        guarded_proc.returncode == 0
    ), "the `|| exit 0` guard must make a missing script unable to block"

    # And the guard the installer actually writes must carry it.
    wire = os.path.join(os.path.dirname(os.path.dirname(HOOK)), "bin", "_wire_hook.py")
    src = open(wire, encoding="utf-8").read()
    assert "|| exit 0" in src, "the installer no longer guards its registrations"


def _property_offer_is_recorded_distinctly(fx: HookFixture) -> None:
    # An offer is recorded, distinctly from authorship. Without this the prompt
    # is decoration: nothing can tell an offer that was taken from one that was
    # never made.
    offers = [
        json.loads(line)
        for line in open(
            os.path.join(get_project_dir(fx.root, fx.proj), "authorship.jsonl")
        )
        if json.loads(line).get("event") == "offered"
    ]
    assert offers, "the once-per-session offer was never recorded"
    assert offers[0]["author"] == "grit" and "lines" not in offers[0], (
        "an offer must not look like an authorship row: %s" % offers[0]
    )


def _property_fresh_repo_with_hook_scores(fx: HookFixture) -> None:
    # A fresh repository with a hook wired up but no log yet must read as
    # HUMAN-WRITTEN, not UNVERIFIED. Conflating "nobody watched" with "the
    # watcher saw nothing" made the first task in every new project unscoreable.
    repo2 = tempfile.mkdtemp(prefix="grit-fresh-")
    root2 = tempfile.mkdtemp(prefix="grit-fresh-root-")
    try:
        _init_repo(repo2)
        skill = os.path.join(os.path.dirname(os.path.dirname(HOOK)), "skills", "grit")
        sys.path.insert(0, skill)
        import doctor

        watching = doctor.is_watching(repo2)

        _verify_edit_cmd(repo2, "snapshot", "f1", root=root2)
        open(os.path.join(repo2, "a.py"), "a").write("y=2\n")
        rc = _verify_edit_cmd(repo2, "verify", "f1", root=root2)

        assert not os.path.exists(
            os.path.join(get_project_dir(root2, repo2), "authorship.jsonl")
        ), "precondition: this repo should have no authorship log"
        expected = 0 if watching else 3
        assert rc == expected, "fresh repo with watching=%s should give %d, got %d" % (
            watching,
            expected,
            rc,
        )
    finally:
        shutil.rmtree(repo2, ignore_errors=True)
        shutil.rmtree(root2, ignore_errors=True)


def _property_declined_offer_counts_as_taken(fx: HookFixture) -> None:
    # `taken` — the dashboard's "you took over" tile — was 0 on every machine
    # that ever ran this. The hook logged the edit that raised the offer as an
    # assistant edit in the same session, and `taken` is "offered, and no
    # assistant edit followed", so no session could ever qualify.
    root = tempfile.mkdtemp(prefix="grit-taken-root-")
    proj = tempfile.mkdtemp(prefix="grit-taken-")
    try:
        f = HookFixture(root=root, proj=proj)
        # Declined: the one prompted edit, then only shell (the assistant
        # running the user's tests), which is the DIY case working.
        f.run(f.write_event(session="declined"))
        f.run(f.event("Bash", session="declined", command="npm test"))
        # Approved: the assistant carried on writing files.
        f.run(f.write_event(session="approved"))
        f.run(f.write_event(name="b.py", content="more\n", session="approved"))
        # Approved, and nothing after it. Only PostToolUse can tell this from
        # declined — the inference alone read it as taken.
        quiet = f.write_event(name="c.py", session="quiet")
        f.run(quiet)
        f.run(dict(quiet, hook_event_name="PostToolUse"))

        skill = os.path.join(os.path.dirname(os.path.dirname(HOOK)), "skills", "grit")
        sys.path.insert(0, skill)
        import serve

        totals = serve.State(root).authorship()["totals"]
        assert totals["offers"] == 3, totals
        assert totals["taken"] == 1, "only the declined session was taken: %s" % totals
        # The prompted edit still counts as the assistant's — PreToolUse fires
        # before the answer, and over-counting the assistant is the safe side.
        assert totals["edits"] == 4 and totals["shell"] == 1, totals
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)


def _property_post_tool_use_confirms_without_counting(fx: HookFixture) -> None:
    # PostToolUse carries the same tool_input as the PreToolUse before it. If
    # it were read as an edit, every write would count twice; if it could ask,
    # the user would be prompted after the fact.
    root = tempfile.mkdtemp(prefix="grit-post-root-")
    proj = tempfile.mkdtemp(prefix="grit-post-")
    try:
        f = HookFixture(root=root, proj=proj)
        edit = f.write_event(session="p1")
        f.run(edit)
        assert f.run(dict(edit, hook_event_name="PostToolUse")) == "", "a post event asked"
        assert f.count_rows() == 1, "the post event was counted as authorship"
        applied = [r for r in f.rows(author="grit") if r.get("event") == "applied"]
        assert len(applied) == 1, "the post event was not recorded: %s" % applied
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)


def _property_verdicts_are_recorded_per_task(fx: HookFixture) -> None:
    # A verdict used to exist only as an exit code and an evidence row, so the
    # dashboard could not say which tasks the user did and which the assistant
    # did. The record is written by verify_edit itself, never by the assistant.
    repo = tempfile.mkdtemp(prefix="grit-tasks-")
    root = tempfile.mkdtemp(prefix="grit-tasks-root-")
    try:
        _init_repo(repo)
        _verify_edit_cmd(repo, "snapshot", "t1", root=root)
        with open(os.path.join(repo, "new file.py"), "w") as fh:
            fh.write("a=1\nb=2\n")
        open(os.path.join(repo, "a.py"), "a").write("c=3\n")
        _verify_edit_cmd(repo, "verify", "t1", root=root)
        _verify_edit_cmd(repo, "verify", "t1", root=root)  # a re-run appends

        log = os.path.join(get_project_dir(root, repo), "tasks.jsonl")
        runs = [json.loads(line) for line in open(log)]
        assert len(runs) == 2, "a re-verify must append, never rewrite: %s" % runs
        # 2 lines in an untracked file (with a space in its name) + 1 tracked.
        assert runs[-1]["lines_added"] == 3 and runs[-1]["files_changed"] == 2, runs[-1]

        skill = os.path.join(os.path.dirname(os.path.dirname(HOOK)), "skills", "grit")
        sys.path.insert(0, skill)
        import serve

        state = serve.State(root)
        _write_projects(root, [os.path.realpath(repo)])
        view = state.tasks()
        assert len(view["tasks"]) == 1, "the view shows each task's latest run once"
        assert sum(view["totals"].values()) == 1, view["totals"]
        # The trend keeps empty weeks — a gap is part of it — and counts each
        # task once, in the week of its latest run.
        assert len(view["weeks"]) == 8, view["weeks"]
        assert sum(sum(w["verdicts"].values()) for w in view["weeks"]) == 1, view["weeks"]
        assert view["weeks"][-1]["verdicts"], "this week's task is missing"
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


def _write_projects(root: str, paths: list[str]) -> None:
    with open(os.path.join(root, "projects.json"), "w") as fh:
        json.dump(paths, fh)


def _property_installer_registers_and_removes_both_events(fx: HookFixture) -> None:
    # PostToolUse is what makes "taken" an observation. An install that wrote
    # only PreToolUse would silently fall back to the inference; an uninstall
    # that removed only PreToolUse would leave a hook behind in the user's file.
    wire = os.path.join(os.path.dirname(os.path.dirname(HOOK)), "bin", "_wire_hook.py")
    tmp = tempfile.mkdtemp(prefix="grit-wire-")
    try:
        cfg = os.path.join(tmp, "settings.json")
        with open(cfg, "w") as fh:
            json.dump({"hooks": {"PostToolUse": [{"matcher": "X", "hooks": [
                {"type": "command", "command": "echo mine"}]}]}}, fh)
        sp.run([sys.executable, wire, "claude", cfg, HOOK, "install"], check=True,
               capture_output=True)
        hooks = json.load(open(cfg))["hooks"]
        assert len(hooks["PreToolUse"]) == 2 and len(hooks["PostToolUse"]) == 3, hooks
        sp.run([sys.executable, wire, "claude", cfg, HOOK, "remove"], check=True,
               capture_output=True)
        hooks = json.load(open(cfg))["hooks"]
        assert "PreToolUse" not in hooks, hooks
        assert [g["matcher"] for g in hooks["PostToolUse"]] == ["X"], (
            "uninstall touched a hook that is not ours: %s" % hooks
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _property_distinct_shell_calls_are_not_merged(fx: HookFixture) -> None:
    # The dedupe fingerprint ignored `command`, so every shell call in a session
    # hashed alike and distinct calls under 250ms apart — a parallel batch —
    # became one row. A simulated session lost 3 of its 5 shell calls.
    root = tempfile.mkdtemp(prefix="grit-dedupe-root-")
    proj = tempfile.mkdtemp(prefix="grit-dedupe-")
    try:
        f = HookFixture(root=root, proj=proj)
        for cmd in ("ls", "npm test", "git status"):
            f.run(f.event("Bash", command=cmd))
        assert f.count_rows() == 3, "distinct shell calls were merged: %d" % f.count_rows()
        # Two registrations of ONE call still count once.
        call = dict(f.event("Bash", command="make"), tool_use_id="u1")
        f.run(call)
        f.run(call)
        assert f.count_rows() == 4, "one call, two registrations, counted twice"
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)


def _shell_call(f: HookFixture, repo: str, call: str, command: str, effect=None) -> None:
    """One assistant shell call as the runtime delivers it: Pre, run, Post."""
    event = {"tool_name": "Bash", "session_id": "sh", "cwd": repo,
             "tool_use_id": call, "tool_input": {"command": command}}
    f.run(dict(event, hook_event_name="PreToolUse"))
    if effect:
        effect()
    f.run(dict(event, hook_event_name="PostToolUse"))


def _property_observed_shell_calls_do_not_void_the_task(fx: HookFixture) -> None:
    # The skill tells the assistant to run the user's check and verify_edit
    # itself through the shell. Each call was opaque, so EVERY task done through
    # the skill came out UNVERIFIED and scored zero — found by simulating a real
    # session end to end. The hook now watches the tree around a shell call.
    repo = tempfile.mkdtemp(prefix="grit-shell-")
    root = tempfile.mkdtemp(prefix="grit-shell-root-")
    try:
        _init_repo(repo)
        f = HookFixture(root=root, proj=repo)
        _verify_edit_cmd(repo, "snapshot", "h1", root=root)
        open(os.path.join(repo, "a.py"), "a").write("human=1\n")  # the user
        _shell_call(f, repo, "c1", "python3 -m pytest")  # reads, writes nothing
        assert _verify_edit_cmd(repo, "verify", "h1", root=root) == 0, (
            "a shell call observed writing nothing must not void the task"
        )

        _verify_edit_cmd(repo, "snapshot", "h2", root=root)
        open(os.path.join(repo, "a.py"), "a").write("human=2\n")
        write = lambda: open(os.path.join(repo, "gen.py"), "w").write("x=1\n")
        _shell_call(f, repo, "c2", "python3 - <<EOF ...", effect=write)
        assert _verify_edit_cmd(repo, "verify", "h2", root=root) == 1, (
            "a shell call observed writing a file is the assistant's work"
        )

        # And a commit is not authorship: content untouched, status clean.
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        _verify_edit_cmd(repo, "snapshot", "h3", root=root)
        open(os.path.join(repo, "a.py"), "a").write("human=3\n")
        commit = lambda: subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "w"],
            cwd=repo, check=True)
        _shell_call(f, repo, "c3", "git commit -am w", effect=commit)
        assert _verify_edit_cmd(repo, "verify", "h3", root=root) == 0, (
            "committing the user's work is not writing it"
        )

        # verify_edit is itself run through the shell, so its own call is
        # always in flight while it reads the log. Excused only when the
        # command is nothing but that invocation.
        for command, expected in (
            ("python3 /x/verify_edit.py verify h5", 0),
            ("python3 /x/verify_edit.py verify h5 $(touch z)", 3),
        ):
            _verify_edit_cmd(repo, "snapshot", "h5", root=root)
            open(os.path.join(repo, "a.py"), "a").write("human=5\n")
            f.run({"tool_name": "Bash", "session_id": "sh", "cwd": repo,
                   "tool_use_id": "v-" + str(expected), "hook_event_name": "PreToolUse",
                   "tool_input": {"command": command}})
            assert _verify_edit_cmd(repo, "verify", "h5", root=root) == expected, (
                "in-flight %r should give %d" % (command, expected)
            )

        # With no Post (an older install), the call stays unobserved.
        _verify_edit_cmd(repo, "snapshot", "h4", root=root)
        open(os.path.join(repo, "a.py"), "a").write("human=4\n")
        f.run({"tool_name": "Bash", "session_id": "sh", "cwd": repo, "tool_use_id": "c4",
               "hook_event_name": "PreToolUse", "tool_input": {"command": "ls"}})
        assert _verify_edit_cmd(repo, "verify", "h4", root=root) == 3, (
            "a shell call nobody saw finish must stay UNVERIFIED"
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
