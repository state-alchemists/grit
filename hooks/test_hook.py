#!/usr/bin/env python3
"""Self-check for the hook. Run: python3 hooks/test_hook.py

The hook exits 0 no matter what, so "it ran" proves nothing — these assert on
what it actually did. The JSON is built with json.dumps, never with a shell
echo: an earlier version of this test used `echo` and the shell turned "\\n"
into real newlines, producing invalid JSON that the hook swallowed silently.
"""

import json
import os
import shutil
import subprocess as sp
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grit-hook.py")


def rows(proj, author="assistant"):
    """Authorship rows only. The log also carries `offered` events now, and a
    count that includes them reads an offer as an edit."""
    path = os.path.join(proj, ".grit", "authorship.jsonl")
    out = []
    with open(path) as fh:
        for line in fh:
            r = json.loads(line)
            if author is None or r.get("author") == author:
                out.append(r)
    return out


def run(event, root, env=None):
    e = dict(os.environ, GRIT_ROOT=root)
    e.update(env or {})
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                       capture_output=True, text=True, env=e)
    assert p.returncode == 0, "hook must always exit 0, got %d" % p.returncode
    return p.stdout.strip()


def main():
    root = tempfile.mkdtemp(prefix="grit-hookroot-")
    proj = tempfile.mkdtemp(prefix="grit-proj-")
    try:
        write = {"tool_name": "Write", "session_id": "s1", "cwd": proj,
                 "tool_input": {"file_path": proj + "/a.py",
                                "content": "one\ntwo\nthree\n"}}

        # 1. First edit of a session asks, once.
        out = run(write, root)
        assert out, "first write should produce an ask"
        decision = json.loads(out)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "ask", decision
        assert "I'll do it" in decision["permissionDecisionReason"]

        # 2. Second edit in the same session is silent. A prompt on every edit
        #    is how a tool gets uninstalled.
        assert run(dict(write, tool_input={"file_path": proj + "/b.py",
                                           "content": "x\n"}), root) == "", \
            "hook asked twice in one session"

        # 3. ...but it still records. Authorship is the number that matters.
        seen = rows(proj)
        assert len(seen) == 2, "expected 2 authorship rows, got %d" % len(seen)
        assert seen[0]["lines"] == 3 and seen[0]["author"] == "assistant"
        assert seen[1]["lines"] == 1

        # 4. A new session asks again.
        assert run(dict(write, session_id="s2"), root), "new session should ask"

        # 5. Edit uses new_string, not content.
        run({"tool_name": "Edit", "session_id": "s3", "cwd": proj,
             "tool_input": {"file_path": proj + "/c.py",
                            "new_string": "p\nq\n"}}, root)
        seen = rows(proj)
        assert seen[-1]["lines"] == 2, "Edit line count wrong: %s" % seen[-1]

        # 6. Tools that do not write code are ignored entirely.
        before = len(seen)
        run({"tool_name": "Read", "session_id": "s4", "cwd": proj,
             "tool_input": {"file_path": proj + "/a.py"}}, root)
        after = len(rows(proj))
        assert after == before, "Read should not be recorded"

        # 7. Both off switches actually stop it.
        assert run(dict(write, session_id="s5"), root,
                   {"GRIT_OFF": "1"}) == "", "GRIT_OFF did not silence the hook"
        open(os.path.join(proj, ".grit", "off"), "w").close()
        assert run(dict(write, session_id="s6"), root) == "", \
            ".grit/off did not silence the hook"
        os.remove(os.path.join(proj, ".grit", "off"))

        # 8. ask_on_first_edit:false keeps recording, drops the prompt.
        with open(os.path.join(root, "preferences.json"), "w") as fh:
            json.dump({"ask_on_first_edit": False}, fh)
        n = len(rows(proj))
        assert run(dict(write, session_id="s7"), root) == "", \
            "ask_on_first_edit:false should suppress the prompt"
        assert len(rows(proj)) == n + 1, \
            "recording must continue when only the prompt is disabled"

        # 9. The same edit arriving twice is counted once. Two registrations
        #    matching one event is normal (user + project level, or zrb reading
        #    Claude's settings.json on top of its own hooks.json) — and would
        #    otherwise inflate the one number that must not be inflatable.
        dup = {"tool_name": "Write", "session_id": "s8", "cwd": proj,
               "tool_input": {"file_path": proj + "/dup.py", "content": "k\n"}}
        n = len(rows(proj))
        run(dup, root); run(dup, root)
        assert len(rows(proj)) == n + 1, \
            "a doubly-registered hook double-counted one edit"

        # 10. Garbage in never costs the user an edit — and is not silent.
        p = subprocess.run([sys.executable, HOOK], input="not json at all",
                           capture_output=True, text=True,
                           env=dict(os.environ, GRIT_ROOT=root))
        assert p.returncode == 0, "malformed input must still exit 0"
        assert os.path.exists(os.path.join(root, "hook-errors.log")), \
            "a swallowed failure must leave a trace"

        # 11. verify_edit distinguishes the four outcomes, and never upgrades
        #     "nobody was watching" into "the human wrote it".
        import subprocess as sp
        V = os.path.join(os.path.dirname(os.path.dirname(HOOK)),
                         "skills", "grit", "verify_edit.py")
        repo = tempfile.mkdtemp(prefix="grit-git-")
        try:
            for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
                        ["git", "config", "user.name", "t"]):
                sp.run(cmd, cwd=repo, capture_output=True)
            open(os.path.join(repo, "a.py"), "w").write("x=1\n")
            sp.run(["git", "add", "-A"], cwd=repo, capture_output=True)
            sp.run(["git", "commit", "-qm", "i"], cwd=repo, capture_output=True)

            def ve(*a):
                return sp.run([sys.executable, V, *a, repo], cwd=repo,
                              capture_output=True, text=True).returncode

            ve("snapshot", "t1")
            assert ve("verify", "t1") == 2, "no change must not read as earned"

            open(os.path.join(repo, "a.py"), "a").write("y=2\n")
            # With NO hook registered anywhere this is UNVERIFIED; with one
            # registered it is HUMAN-WRITTEN, because a watching hook that
            # recorded nothing is evidence the assistant wrote nothing. The
            # test machine may be either, so ask before asserting.
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.dirname(HOOK)), "skills", "grit"))
            import doctor
            assert ve("verify", "t1") == (0 if doctor.is_watching(repo) else 3), \
                "verdict must follow whether a hook is actually watching"

            os.makedirs(os.path.join(repo, ".grit"), exist_ok=True)
            open(os.path.join(repo, ".grit", "authorship.jsonl"), "w").close()
            ve("snapshot", "t2")
            open(os.path.join(repo, "a.py"), "a").write("z=3\n")
            assert ve("verify", "t2") == 0, "human edit with a live log = earned"

            # ...but an unobserved shell call in the same window must knock the
            # verdict back to UNVERIFIED. "No edits observed" is not proof of a
            # human author when the assistant also ran a shell.
            ve("snapshot", "t3")
            sp.run([sys.executable, HOOK], cwd=repo, text=True,
                   input=json.dumps({"tool_name": "Bash", "session_id": "z",
                                     "cwd": repo,
                                     "tool_input": {"command": "sed -i s/x/y/ a.py"}}),
                   capture_output=True, env=dict(os.environ, GRIT_ROOT=root))
            open(os.path.join(repo, "a.py"), "a").write("w=4\n")
            assert ve("verify", "t3") == 3, \
                "a shell call in the window must force UNVERIFIED"
        finally:
            shutil.rmtree(repo, ignore_errors=True)

        # 12. A Bash call is recorded as opaque, never as "wrote nothing",
        #     and never prompts. This is the blind spot that made an assistant
        #     editing via `python3 - <<EOF` look like a human author.
        bash = {"tool_name": "Bash", "session_id": "s9", "cwd": proj,
                "tool_input": {"command": "sed -i s/a/b/ x.py"}}
        n = sum(1 for l in open(os.path.join(proj, ".grit", "authorship.jsonl"))
                if json.loads(l).get("author") == "assistant")
        assert run(bash, root) == "", "Bash must never trigger the prompt"
        seen = rows(proj)
        assert len(seen) == n + 1, "Bash call was not recorded at all"
        assert seen[-1]["opaque"] is True and "lines" not in seen[-1], \
            "a shell call must be opaque, not a zero line count: %s" % seen[-1]

        # 13. A registration whose script is GONE must not block the tool call.
        #     Python exits 2 when it cannot open a file, and 2 is exactly the
        #     code both zrb and Claude Code read as "block this tool call" — so
        #     an unguarded registration with a stale path silently kills every
        #     Write and Edit in the project. This shipped, and cost a session.
        import shlex as _shlex
        missing = "python3 " + _shlex.quote(root + "/gone.py")
        raw = sp.run(missing, shell=True, input="{}", text=True,
                     capture_output=True)
        assert raw.returncode == 2, \
            "precondition: a missing script should exit 2 (got %d)" % raw.returncode
        guarded = sp.run(missing + " || exit 0", shell=True, input="{}",
                         text=True, capture_output=True)
        assert guarded.returncode == 0, \
            "the `|| exit 0` guard must make a missing script unable to block"

        # And the guard the installer actually writes must carry it.
        wire = os.path.join(os.path.dirname(os.path.dirname(HOOK)),
                            "bin", "_wire_hook.py")
        src = open(wire, encoding="utf-8").read()
        assert "|| exit 0" in src, \
            "the installer no longer guards its registrations"

        # 14. An offer is recorded, distinctly from authorship. Without this the
        #     prompt is decoration: nothing can tell an offer that was taken
        #     from one that was never made.
        offers = [json.loads(l) for l
                  in open(os.path.join(proj, ".grit", "authorship.jsonl"))
                  if json.loads(l).get("event") == "offered"]
        assert offers, "the once-per-session offer was never recorded"
        assert offers[0]["author"] == "grit" and "lines" not in offers[0], \
            "an offer must not look like an authorship row: %s" % offers[0]

        # 15. A fresh repository with a hook wired up but no log yet must read
        #     as HUMAN-WRITTEN, not UNVERIFIED. Conflating "nobody watched"
        #     with "the watcher saw nothing" made the first task in every new
        #     project unscoreable.
        repo2 = tempfile.mkdtemp(prefix="grit-fresh-")
        try:
            for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
                        ["git", "config", "user.name", "t"]):
                sp.run(cmd, cwd=repo2, capture_output=True)
            open(os.path.join(repo2, "a.py"), "w").write("x=1\n")
            sp.run(["git", "add", "-A"], cwd=repo2, capture_output=True)
            sp.run(["git", "commit", "-qm", "i"], cwd=repo2, capture_output=True)

            skill = os.path.join(os.path.dirname(os.path.dirname(HOOK)),
                                 "skills", "grit")
            sys.path.insert(0, skill)
            import doctor
            watching = doctor.is_watching(repo2)

            sp.run([sys.executable, os.path.join(skill, "verify_edit.py"),
                    "snapshot", "f1", repo2], cwd=repo2, capture_output=True)
            open(os.path.join(repo2, "a.py"), "a").write("y=2\n")
            rc = sp.run([sys.executable, os.path.join(skill, "verify_edit.py"),
                         "verify", "f1", repo2], cwd=repo2,
                        capture_output=True).returncode
            assert not os.path.exists(os.path.join(repo2, ".grit",
                                                   "authorship.jsonl")), \
                "precondition: this repo should have no authorship log"
            expected = 0 if watching else 3
            assert rc == expected, (
                "fresh repo with watching=%s should give %d, got %d"
                % (watching, expected, rc))
        finally:
            shutil.rmtree(repo2, ignore_errors=True)

        print("ok — 15 properties hold")
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(proj, ignore_errors=True)


if __name__ == "__main__":
    main()
