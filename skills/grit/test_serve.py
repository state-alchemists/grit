#!/usr/bin/env python3
"""Self-check for the daemon. Run: python3 skills/grit/test_serve.py

No framework, no fixtures. One assert per property that, if it broke, would
make the dashboard lie. Every case here is a bug that actually shipped — the
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
from http.server import ThreadingHTTPServer
from threading import Thread
from typing import Any

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


@dataclass
class Fixture:
    """A running daemon on an ephemeral port, with its root."""

    state: serve.State
    base: str
    root: str
    port: int

def main() -> None:
    root = tempfile.mkdtemp(prefix="grit-test-")
    try:
        fx = _start_daemon(root)

        # A list, so the printed count is the number of properties that ran.
        # It previously said 7 while calling 13 — and AGENTS.md, README.md and
        # .sdlc/docs/dev-fixtures.md all quote that figure, so the drift was in four
        # places at once.
        properties = [
            lambda: _property_port_is_published(fx),
            lambda: _property_hidden_guard_precedes_display(fx),
            lambda: _property_dashboard_endpoints_answer(fx),
            lambda: _property_sibling_import_does_not_leak_path(fx, root),
            lambda: _property_preferences_round_trip(fx),
            lambda: _property_mechanism_off_is_visible(fx, root),
            lambda: _property_detached_daemon_starts_on_a_fresh_root(root),
        ]
        for check in properties:
            check()
        print("ok — %d properties hold" % len(properties))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _property_detached_daemon_starts_on_a_fresh_root(root: str) -> None:
    # `serve.py --root ~/.grit --daemon` is the README's first command, and on
    # a machine where ~/.grit did not exist yet it crashed opening daemon.log —
    # the foreground path created the root, the detached one did not.
    import subprocess

    fresh = os.path.join(root, "not-yet-created")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serve.py")
    run = lambda *a: subprocess.run(
        [sys.executable, script, "--root", fresh, *a], capture_output=True, text=True
    )
    started = run("--port", "0", "--daemon")
    try:
        assert started.returncode == 0, "--daemon failed on a fresh root: %s" % started.stderr
        assert os.path.exists(os.path.join(fresh, "daemon.json")), "no address published"
    finally:
        run("--stop")


def _start_daemon(root: str) -> Fixture:
    state = serve.State(root)
    serve.Handler.state = state
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
    Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    return Fixture(
        state=state, base="http://127.0.0.1:%d" % port, root=root, port=port
    )


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
    # Shipped bug: SKILL.md and the daemon's own links hard-coded 7801, so
    # anything but the default port handed the user a URL that did not answer.
    assert serve.DEFAULT_PORT, "there must still be a default"
    assert fx.port != serve.DEFAULT_PORT, "test should be on an ephemeral port"
    assert _get(fx.base, "/status")["daemon"]["url"] == fx.base, (
        "the daemon must report its real address, not the default port"
    )


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


if __name__ == "__main__":
    main()
