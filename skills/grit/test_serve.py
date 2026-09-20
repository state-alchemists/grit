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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from threading import Thread
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serve  # noqa: E402


def _post(base: str, path: str, obj: dict[str, Any]) -> tuple[int, Any]:
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


def _get(base: str, path: str) -> Any:
    return json.load(urllib.request.urlopen(base + path))


def _launch(base: str, name: str) -> str:
    """Open a tutorial and return its report token, as the browser would."""
    html = urllib.request.urlopen(base + "/tutorial/" + name).read().decode()
    return html.split("window.GRIT_SESSION=")[1].split(";")[0].strip('"')


@dataclass
class Fixture:
    """A running daemon on an ephemeral port, with its root and report token."""

    state: serve.State
    base: str
    root: str
    port: int

    def report_token(self, name: str = "tb.html") -> str:
        return _launch(self.base, name)

    def launch_and_check(self, name: str = "tb.html", answer: str = "because") -> str:
        """Open a tutorial, pass the check, submit a justification. Returns the
        report token, ready to be judged."""
        tok = self.report_token(name)
        _post(self.base, "/tutorial/%s/check" % tok, {"passed": True})
        _post(self.base, "/tutorial/%s/justification" % tok, {"answer": answer})
        return tok

    def judge_token_for(self, report_token: str) -> str:
        return next(k for k, v in self.state.judge_index.items() if v == report_token)

    def last_entry(self) -> dict[str, Any]:
        return _get(self.base, "/ledger")["entries"][-1]


def main() -> None:
    root = tempfile.mkdtemp(prefix="grit-test-")
    try:
        fx = _start_daemon(root)

        # A list, so the printed count is the number of properties that ran.
        # It previously said 7 while calling 13 — and AGENTS.md, README.md and
        # .sdlc/docs/dev-fixtures.md all quote that figure, so the drift was in four
        # places at once.
        properties = [
            lambda: _property_page_cannot_self_judge(fx),
            lambda: _property_earned_cannot_outlive_check(fx),
            lambda: _property_completed_tutorial_scores(fx),
            lambda: _property_no_credential_in_ledger(fx),
            lambda: _property_unsound_records_failure(fx, root),
            lambda: _property_gate_three_appends(fx),
            lambda: _property_port_is_published(fx),
            lambda: _property_hidden_guard_precedes_display(fx),
            lambda: _property_dashboard_endpoints_answer(fx),
            lambda: _property_sibling_import_does_not_leak_path(fx, root),
            lambda: _property_preferences_round_trip(fx),
            lambda: _property_pending_survives_restart(fx, root),
            lambda: _property_stale_pending_shows_its_age(fx, root),
            lambda: _property_mechanism_off_is_visible(fx, root),
            lambda: _property_prediction_reaches_the_judge(fx, root),
        ]
        for check in properties:
            check()
        print("ok — %d properties hold" % len(properties))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _start_daemon(root: str) -> Fixture:
    os.makedirs(os.path.join(root, "tutorials"), exist_ok=True)
    with open(os.path.join(root, "tutorials", "tb.html"), "w") as fh:
        fh.write("<html><head></head><body>x</body></html>")
    state = serve.State(root)
    serve.Handler.state = state
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
    Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    return Fixture(
        state=state, base="http://127.0.0.1:%d" % port, root=root, port=port
    )


def _property_page_cannot_self_judge(fx: Fixture) -> None:
    # Shipped bug: the report token and the judge token were the same, so
    # the tutorial's own JavaScript could POST {"judgment":"sound"}.
    tok = fx.launch_and_check()
    code, _ = _post(fx.base, "/tutorial/%s/judgment" % tok, {"judgment": "sound"})
    assert code == 403, "page must not reach gate 3, got %s" % code
    assert fx.last_entry()["earned"] is False, "page self-judged its way to earned"

    # The judge token, which never reaches the browser, does work.
    _post(fx.base, "/judgment/%s" % fx.judge_token_for(tok), {"judgment": "sound"})
    assert (
        fx.last_entry()["earned"] is True
    ), "assistant's judgment should close the third gate"


def _property_earned_cannot_outlive_check(fx: Fixture) -> None:
    # Shipped bug: judge() assigned earned=True independently of the check,
    # so re-reporting a failure left earned:true beside check.passed:false.
    tok = fx.launch_and_check()
    _post(fx.base, "/judgment/%s" % fx.judge_token_for(tok), {"judgment": "sound"})
    _post(fx.base, "/tutorial/%s/check" % tok, {"passed": False})
    row = fx.last_entry()
    assert row["earned"] is False, "earned survived a failed check"
    assert row["gates"]["check"]["passed"] is False


def _property_completed_tutorial_scores(fx: Fixture) -> None:
    # The two halves used to be unconnected: the ledger recorded `earned`
    # and the score never heard about it, so finishing a tutorial moved
    # nothing. Proficiency itself is score.py's job and tested there.
    tok = fx.launch_and_check()
    _post(fx.base, "/judgment/%s" % fx.judge_token_for(tok), {"judgment": "sound"})
    prof = _get(fx.base, "/profile")
    assert "tb" in prof["concepts"], (
        "an earned tutorial must produce evidence, got %s" % prof
    )
    assert prof["concepts"]["tb"]["level"] in ("unproven", "recall"), prof
    assert (
        prof["concepts"]["tb"]["unaided_tasks"] == 0
    ), "a sandbox pass is not repository work"


def _property_no_credential_in_ledger(fx: Fixture) -> None:
    # Shipped bug: entries carried the live session token, and /ledger was
    # readable cross-origin — a credential handed to every reader.
    tok = fx.launch_and_check()
    judge_tok = fx.judge_token_for(tok)
    blob = json.dumps(_get(fx.base, "/ledger"))
    assert tok not in blob, "report token leaked into the ledger"
    assert judge_tok not in blob, "judge token leaked into the ledger"


def _property_unsound_records_failure(fx: Fixture, root: str) -> None:
    # Shipped gap: a user passed the check, submitted a justification, was
    # judged unsound — and their profile stayed completely empty. Nothing
    # in the daemon ever wrote the failure event the score model supports.
    tok = fx.launch_and_check(answer="vague")
    _post(fx.base, "/judgment/%s" % fx.judge_token_for(tok), {"judgment": "unsound"})
    import score as _score

    fails = [e for e in _score.load(root) if e.concept == "tb" and e.failed]
    assert fails, "an unsound judgment must record a failure event"
    assert fails[-1].source == "sandbox", fails[-1]


def _property_gate_three_appends(fx: Fixture) -> None:
    # Shipped bug, seen in real use: a judgment was cast with the
    # placeholder message "test", then re-cast with the real reasoning, and
    # the ledger kept no trace of the first. A verdict you can silently
    # overwrite is not evidence.
    tok = fx.launch_and_check(answer="a")
    judge_tok = fx.judge_token_for(tok)
    code1, _ = _post(
        fx.base, "/judgment/%s" % judge_tok, {"judgment": "unsound", "message": "test"}
    )
    assert code1 == 200, code1

    # The correction is accepted as an amendment, and refused as a rewrite.
    code2, body2 = _post(
        fx.base,
        "/judgment/%s" % judge_tok,
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

    rows = [
        e
        for e in _get(fx.base, "/ledger")["entries"]
        if e["gates"].get("judgment", {}).get("message") == "test"
    ]
    assert rows, "the standing verdict must be the one in the ledger"
    assert rows[0]["earned"] is False


def _property_mechanism_off_is_visible(fx: Fixture, root: str) -> None:
    # `visible_overrides` and `default_do_it_myself` sat in DEFAULT_PREFS for
    # weeks with nothing reading, writing or rendering either, so DESIGN's
    # "a preference that turns the mechanism off is recorded and shown" was
    # a key and a sentence. A setting that disables the only function the
    # product has must reach the page, or the product looks fine while doing
    # nothing — which is the exact failure it exists to treat.
    assert not _get(fx.base, "/status")["notices"], "a default setup has nothing to report"
    _post(fx.base, "/preferences", {"default_do_it_myself": False})
    kinds = [n["kind"] for n in _get(fx.base, "/status")["notices"]]
    assert "mechanism-off" in kinds, "opting out by default must be visible: %s" % kinds

    # Opting out is a *setting*, not a measurement. Showing it must not start
    # recording the user — that half was never the disagreement.
    evidence = os.path.join(root, "evidence.jsonl")
    before = os.path.getsize(evidence) if os.path.exists(evidence) else 0
    _get(fx.base, "/status")
    after = os.path.getsize(evidence) if os.path.exists(evidence) else 0
    assert before == after, "reporting the setting must not write evidence"


def _property_port_is_published(fx: Fixture) -> None:
    # Shipped bug: SKILL.md, the tutorial fallback and the judge command all
    # hard-coded 7801, so anything but the default port handed the user a
    # URL that did not answer.
    assert serve.DEFAULT_PORT, "there must still be a default"
    assert fx.port != serve.DEFAULT_PORT, "test should be on an ephemeral port"
    html = urllib.request.urlopen(fx.base + "/tutorial/tb.html").read().decode()
    assert (
        '"%s"' % fx.base
    ) in html, "the daemon must inject its real address, not the default port"


def _property_hidden_guard_precedes_display(fx: Fixture) -> None:
    # Shipped bug: `.veil{display:grid}` is an author rule and beats the
    # UA's `[hidden]{display:none}`, so the onboarding dialog never closed.
    # Save posted fine; the page just never changed, which reads as a dead
    # button. The guard has to sit above every rule that sets `display`.
    page = urllib.request.urlopen(fx.base + "/").read().decode()
    guard = page.find("[hidden]{display:none!important}")
    assert guard != -1, "the [hidden] guard is gone; overlays will not close"
    assert guard < page.find(
        "display:flex"
    ), "the [hidden] guard must precede rules that set display"


def _property_dashboard_endpoints_answer(fx: Fixture) -> None:
    # Shipped regression: `State.authorship()` was deleted as collateral
    # when the superseded profile model was excised — it sat between the
    # block being removed and the next method. `/authorship` then 500'd,
    # and because the page fetches with Promise.all, ONE dead endpoint
    # blanked the WHOLE dashboard. Nothing here tested that route, so it
    # shipped. This list must match what dashboard.html actually calls.
    page = urllib.request.urlopen(fx.base + "/").read().decode()
    called = sorted(set(re.findall(r'getJSON\("(/[a-z]+)"\)', page)))
    assert called, "could not find the dashboard's fetches"
    for ep in called:
        try:
            body = _get(fx.base, ep)
        except Exception as exc:
            raise AssertionError("dashboard fetches %s and it failed: %s" % (ep, exc))
        assert isinstance(body, dict), "%s did not return an object" % ep


def _property_sibling_import_does_not_leak_path(fx: Fixture, root: str) -> None:
    # Shipped bug: `sys.path.insert(0, ...)` ran inside a per-request
    # helper, so a daemon polled every 30s grew sys.path without bound and
    # slowed every import after it. 200 requests measured 200 entries.
    before = len(sys.path)
    for _ in range(50):
        serve._score_profile(root)
    assert (
        len(sys.path) - before <= 1
    ), "sibling import leaked %d sys.path entries" % (len(sys.path) - before)


def _property_preferences_round_trip(fx: Fixture) -> None:
    saved = _post(
        fx.base,
        "/preferences",
        {"theme": "terminal", "callsign": "ada", "onboarded": True},
    )[1]
    assert saved["theme"] == "terminal" and saved["callsign"] == "ada"
    assert (
        _post(fx.base, "/preferences", {"theme": "../etc"})[1]["theme"]
        == serve.DEFAULT_PREFS["theme"]
    ), "unknown theme must fall back"


def _property_prediction_reaches_the_judge(fx: Fixture, root: str) -> None:
    # The prediction is the only thing on the page the user cannot write after
    # seeing the result, which makes it worthless the moment it stops arriving.
    # It rides on gate 2's payload, so a change to JustificationGate that drops
    # the field loses it silently: the judge just sees an answer, exactly as
    # before, with nothing on screen to say a prediction was ever made.
    tok = fx.report_token("tb.html")
    _post(fx.base, "/tutorial/%s/check" % tok, {"passed": True})
    _post(fx.base, "/tutorial/%s/justification" % tok,
          {"answer": "the guard", "prediction": "ZF is 0 so it loops"})
    gate = fx.last_entry()["gates"]["justification"]
    assert gate.get("prediction") == "ZF is 0 so it loops", gate
    # And it must survive the restart that gate 3 may land after.
    reborn = serve.State(root)
    stored = reborn.sessions[tok].gates["justification"]
    assert stored.get("prediction") == "ZF is 0 so it loops", stored

    # A page that never asked must not invent one. An absent prediction is a
    # fact about the attempt, and "" is how it says so.
    tok = fx.report_token("tb.html")
    _post(fx.base, "/tutorial/%s/check" % tok, {"passed": True})
    _post(fx.base, "/tutorial/%s/justification" % tok, {"answer": "no prediction"})
    assert fx.last_entry()["gates"]["justification"]["prediction"] == ""


def _property_pending_survives_restart(fx: Fixture, root: str) -> None:
    # Shipped bug: sessions were RAM-only, so any restart between the
    # justification and the assistant's verdict stranded the concept
    # unearned forever, fixable only by hand-editing the ledger.
    tok = fx.launch_and_check(answer="again")
    judge_tok = fx.judge_token_for(tok)
    reborn = serve.State(root)  # simulate a restart
    assert reborn.judge_index.get(judge_tok) == tok, "sessions did not persist"
    assert reborn.judge(judge_tok, "sound")[1] is None, "cannot judge after restart"


def _property_stale_pending_shows_its_age(fx: Fixture, root: str) -> None:
    # Shipped gap: a verdict that never arrives was indistinguishable from one
    # still in flight. The tutorials table said "awaiting judgment" forever,
    # with nothing to tell the user the assistant still owed them a judgment.
    #
    # Underneath it sat a worse bug: the ledger stores the tutorial's full
    # path, the route passes the bare filename, and the two were compared
    # directly — so NO tutorial ever matched and the table read "not started"
    # for every row. Hand-built entries hid it; this drives the real path.
    def view(opened: str) -> dict[str, str]:
        entry = _get(fx.base, "/ledger")["entries"][-1]
        entry["opened"] = opened
        return serve.State(root).summarise_tutorial("tb.html", [entry])

    tok = fx.launch_and_check(answer="pending forever")
    assert fx.last_entry()["tutorial"].endswith("tb.html"), fx.last_entry()

    # The row must be found at all, from the real ledger.
    assert fx.last_entry()["earned"] is False
    listed = [
        t for t in _get(fx.base, "/tutorials")["tutorials"] if t["name"] == "tb.html"
    ]
    assert listed, "the tutorial should be listed"
    assert listed[0]["detail"] != "no attempts recorded", (
        "a real attempt must not read as 'no attempts recorded' — the ledger "
        "stores a full path and the route passes a filename: %s" % listed[0]
    )

    five_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    stale = view(five_hours_ago)
    assert "5h" in stale["detail"], (
        "a pending judgment older than an hour must say how long it has waited, "
        "got %r" % stale["detail"]
    )
    three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    assert "3d" in view(three_days_ago)["detail"], view(three_days_ago)

    # The fresh case must stay quiet — an age on a just-launched tutorial is
    # noise, not information.
    assert view(datetime.now(timezone.utc).isoformat())["detail"] == (
        "awaiting judgment"
    )


if __name__ == "__main__":
    main()
