#!/usr/bin/env python3
"""Self-check for the daemon. Run: python3 skills/grit/test_serve.py

No framework, no fixtures. One assert per property that, if it broke, would
make the ledger lie. Every case here is a bug that actually shipped — the
comments name which, so a future edit that reintroduces one fails loudly
instead of quietly re-earning concepts nobody earned.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from threading import Thread

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serve  # noqa: E402


def _post(base, path, obj):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req)  # one request, not two
        return resp.getcode(), json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def _get(base, path):
    return json.load(urllib.request.urlopen(base + path))


def _launch(base, name):
    """Open a tutorial and return its report token, as the browser would."""
    html = urllib.request.urlopen(base + "/tutorial/" + name).read().decode()
    return html.split("window.GRIT_SESSION=")[1].split(";")[0].strip('"')


def main():
    root = tempfile.mkdtemp(prefix="grit-test-")
    try:
        os.makedirs(os.path.join(root, "tutorials"), exist_ok=True)
        with open(os.path.join(root, "tutorials", "tb.html"), "w") as fh:
            fh.write("<html><head></head><body>x</body></html>")

        state = serve.State(root)
        serve.Handler.state = state
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        Thread(target=httpd.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % httpd.server_address[1]

        # ── 1. The page cannot award itself gate 3 ───────────────────────────
        # Shipped bug: the report token and the judge token were the same, so
        # the tutorial's own JavaScript could POST {"judgment":"sound"}.
        tok = _launch(base, "tb.html")
        _post(base, "/tutorial/%s/check" % tok, {"passed": True})
        _post(base, "/tutorial/%s/justification" % tok, {"answer": "because..."})
        code, body = _post(base, "/tutorial/%s/judgment" % tok, {"judgment": "sound"})
        assert code == 403, "page must not reach gate 3, got %s" % code
        assert (
            _get(base, "/ledger")["entries"][-1]["earned"] is False
        ), "page self-judged its way to earned"

        # The judge token, which never reaches the browser, does work.
        judge_tok = next(k for k, v in state.judge_index.items() if v == tok)
        _post(base, "/judgment/%s" % judge_tok, {"judgment": "sound"})
        assert (
            _get(base, "/ledger")["entries"][-1]["earned"] is True
        ), "assistant's judgment should close the third gate"

        # ── 2. `earned` cannot outlive a passing check ───────────────────────
        # Shipped bug: judge() assigned earned=True independently of the check,
        # so re-reporting a failure left earned:true beside check.passed:false.
        _post(base, "/tutorial/%s/check" % tok, {"passed": False})
        row = _get(base, "/ledger")["entries"][-1]
        assert row["earned"] is False, "earned survived a failed check"
        assert row["gates"]["check"]["passed"] is False

        # ── 3. A completed tutorial becomes scored evidence ──────────────────
        # The two halves used to be unconnected: the ledger recorded `earned`
        # and the score never heard about it, so finishing a tutorial moved
        # nothing. Proficiency itself is score.py's job and tested there.
        prof = _get(base, "/profile")
        assert "tb" in prof["concepts"], (
            "an earned tutorial must produce evidence, got %s" % prof
        )
        assert prof["concepts"]["tb"]["level"] in ("unproven", "recall"), prof
        assert (
            prof["concepts"]["tb"]["unaided_tasks"] == 0
        ), "a sandbox pass is not repository work"

        # ── 4. No raw credential is readable from the ledger ─────────────────
        # Shipped bug: entries carried the live session token, and /ledger was
        # readable cross-origin — a credential handed to every reader.
        blob = json.dumps(_get(base, "/ledger"))
        assert tok not in blob, "report token leaked into the ledger"
        assert judge_tok not in blob, "judge token leaked into the ledger"

        # ── 3b. An UNSOUND judgment records a FAILURE, not silence ───────────
        # Shipped gap: a user passed the check, submitted a justification, was
        # judged unsound — and their profile stayed completely empty. Nothing
        # in the daemon ever wrote the failure event the score model supports.
        t_un = _launch(base, "tb.html")
        _post(base, "/tutorial/%s/check" % t_un, {"passed": True})
        _post(base, "/tutorial/%s/justification" % t_un, {"answer": "vague"})
        j_un = next(k for k, v in state.judge_index.items() if v == t_un)
        _post(base, "/judgment/%s" % j_un, {"judgment": "unsound"})
        import score as _score

        fails = [
            e for e in _score.load(root) if e.get("concept") == "tb" and e.get("failed")
        ]
        assert fails, "an unsound judgment must record a failure event"
        assert fails[-1]["source"] == "sandbox", fails[-1]

        # ── 3c. Gate 3 appends; the first verdict stands ─────────────────────
        # Shipped bug, seen in real use: a judgment was cast with the
        # placeholder message "test", then re-cast with the real reasoning, and
        # the ledger kept no trace of the first. A verdict you can silently
        # overwrite is not evidence.
        t_am = _launch(base, "tb.html")
        _post(base, "/tutorial/%s/check" % t_am, {"passed": True})
        _post(base, "/tutorial/%s/justification" % t_am, {"answer": "a"})
        j_am = next(k for k, v in state.judge_index.items() if v == t_am)

        code1, _ = _post(
            base, "/judgment/%s" % j_am, {"judgment": "unsound", "message": "test"}
        )
        assert code1 == 200, code1

        # The correction is accepted as an amendment, and refused as a rewrite.
        code2, body2 = _post(
            base,
            "/judgment/%s" % j_am,
            {"judgment": "sound", "message": "real reasoning"},
        )
        assert code2 == 409, "a second verdict must not silently succeed"
        assert body2["standing"] == "unsound", (
            "the FIRST verdict must stand, got %s" % body2["standing"]
        )
        assert body2["standing_message"] == "test", body2
        assert len(body2["judgments"]) == 2, (
            "both verdicts must be kept for audit: %s" % body2["judgments"]
        )
        assert body2["earned"] is False, "an amendment must not flip earned"

        row = [
            e
            for e in _get(base, "/ledger")["entries"]
            if e["gates"].get("judgment", {}).get("message") == "test"
        ]
        assert row, "the standing verdict must be the one in the ledger"
        assert row[0]["earned"] is False

        # ── 4b. The bound port is published, never assumed ───────────────────
        # Shipped bug: SKILL.md, the tutorial fallback and the judge command all
        # hard-coded 7801, so anything but the default port handed the user a
        # URL that did not answer.
        import serve as _s

        assert _s.DEFAULT_PORT, "there must still be a default"
        port = httpd.server_address[1]
        assert port != _s.DEFAULT_PORT, "test should be on an ephemeral port"
        html = urllib.request.urlopen(base + "/tutorial/tb.html").read().decode()
        assert (
            '"%s"' % base
        ) in html, "the daemon must inject its real address, not the default port"

        # ── 4c. The overlay must obey the `hidden` attribute ─────────────────
        # Shipped bug: `.veil{display:grid}` is an author rule and beats the
        # UA's `[hidden]{display:none}`, so the onboarding dialog never closed.
        # Save posted fine; the page just never changed, which reads as a dead
        # button. The guard has to sit above every rule that sets `display`.
        page = urllib.request.urlopen(base + "/").read().decode()
        guard = page.find("[hidden]{display:none!important}")
        assert guard != -1, "the [hidden] guard is gone; overlays will not close"
        assert guard < page.find(
            "display:flex"
        ), "the [hidden] guard must precede rules that set display"

        # ── 4d. EVERY endpoint the dashboard fetches must answer ─────────────
        # Shipped regression: `State.authorship()` was deleted as collateral
        # when the superseded profile model was excised — it sat between the
        # block being removed and the next method. `/authorship` then 500'd,
        # and because the page fetches with Promise.all, ONE dead endpoint
        # blanked the WHOLE dashboard. Nothing here tested that route, so it
        # shipped. This list must match what dashboard.html actually calls.
        page = urllib.request.urlopen(base + "/").read().decode()
        called = sorted(set(re.findall(r'getJSON\("(/[a-z]+)"\)', page)))
        assert called, "could not find the dashboard's fetches"
        for ep in called:
            try:
                body = _get(base, ep)
            except Exception as exc:
                raise AssertionError(
                    "dashboard fetches %s and it failed: %s" % (ep, exc)
                )
            assert isinstance(body, dict), "%s did not return an object" % ep

        # ── 4e. Sibling imports must not leak sys.path ───────────────────────
        # Shipped bug: `sys.path.insert(0, ...)` ran inside a per-request
        # helper, so a daemon polled every 30s grew sys.path without bound and
        # slowed every import after it. 200 requests measured 200 entries.
        before = len(sys.path)
        for _ in range(50):
            serve._score_profile(root)
        assert (
            len(sys.path) - before <= 1
        ), "sibling import leaked %d sys.path entries" % (len(sys.path) - before)

        # ── 5. Preferences round-trip, and an unknown theme is refused ───────
        saved = _post(
            base,
            "/preferences",
            {"theme": "terminal", "callsign": "ada", "onboarded": True},
        )[1]
        assert saved["theme"] == "terminal" and saved["callsign"] == "ada"
        assert (
            _post(base, "/preferences", {"theme": "../etc"})[1]["theme"]
            == serve.DEFAULT_PREFS["theme"]
        ), "unknown theme must fall back"

        # ── 6. A pending judgment survives a daemon restart ──────────────────
        # Shipped bug: sessions were RAM-only, so any restart between the
        # justification and the assistant's verdict stranded the concept
        # unearned forever, fixable only by hand-editing the ledger.
        t2 = _launch(base, "tb.html")
        _post(base, "/tutorial/%s/check" % t2, {"passed": True})
        _post(base, "/tutorial/%s/justification" % t2, {"answer": "again"})
        j2 = next(k for k, v in state.judge_index.items() if v == t2)
        reborn = serve.State(root)  # simulate a restart
        assert reborn.judge_index.get(j2) == t2, "sessions did not persist"
        assert reborn.judge(j2, "sound")[1] is None, "cannot judge after restart"

        print("ok — 6 properties hold")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
