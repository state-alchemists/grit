#!/usr/bin/env python3
"""
grit serve — the local daemon (ADR 0005).

Owns two things the browser cannot:
  1. The tutorial SESSION. A single-use token minted per concept, so a report
     can be traced to the launch that issued it.
  2. The LEDGER. The page never writes it; only this process does.

Binds to loopback only, and serves no cross-origin requests: every page that
talks to it is a page it served itself.

TWO credentials per session. The page gets a REPORT token (gates 1 and 2 only).
The assistant gets a JUDGE token, printed to this process's stderr, for gate 3.
One shared token let the page award itself the judgment.

Run:  python3 serve.py [--port N|0] [--host H] [--root DIR]
      Env: GRIT_PORT, GRIT_HOST, GRIT_ROOT. The bound address is published
      to <root>/daemon.json so nothing downstream has to guess it.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import secrets
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import ModuleType
from typing import Any, Callable, Literal, Optional, cast

# ── The three gates (ADR 0005) ───────────────────────────────────────────────
# A concept is earned only when all three hold. Kept explicit so the ordering
# cannot drift as the code changes.
Gate = Literal["check", "justification", "judgment"]
GATES: tuple[Gate, ...] = ("check", "justification", "judgment")

# Verdicts a judgment gate may return. "pending" is not earned.
JudgmentVerdict = Literal["sound", "unsound", "pending"]
JUDGMENTS: tuple[JudgmentVerdict, ...] = ("sound", "unsound", "pending")

# Default only. Override with --port or GRIT_PORT; --port 0 takes any free port.
# Whatever is actually bound gets written to <root>/daemon.json, and everything
# downstream reads that rather than assuming this number.
DEFAULT_PORT: int = int(os.environ.get("GRIT_PORT", 4748))  # GRIT on a phone keypad

# ── Dashboard themes (chosen at onboarding) ──────────────────────────────────
# Names only; the palettes live in dashboard.html. Kept here so the daemon can
# reject an unknown theme rather than serve a page with no colours.
THEMES: tuple[str, ...] = (
    "dungeon",
    "terminal",
    "synthwave",
    "forest",
    "arcade",
    "paper",
)

DEFAULT_PREFS: dict[str, Any] = {
    "version": 1,
    "onboarded": False,
    "theme": "dungeon",
    "callsign": "",
    "motion": True,  # animations; off is a real accessibility need
    "ask_on_first_edit": True,  # the PreToolUse hook's one prompt per session
    "format": "socratic",
    "depth": "standard",
    "pace": "one-at-a-time",
    "default_do_it_myself": True,
}


# ── Ledger records ───────────────────────────────────────────────────────────
# These mirror the JSON on disk exactly. They are NOT the storage format — the
# ledger stays a plain dict tree, because `check_docs.py` reads it as text and
# older rows must stay readable. These give the shape a name for the code that
# touches it.
def main() -> int:
    ap = argparse.ArgumentParser(description="grit local daemon")
    ap.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GRIT_PORT", DEFAULT_PORT)),
        help="0 picks any free port; the real one is written to daemon.json",
    )
    ap.add_argument(
        "--root", default=os.path.expanduser(os.environ.get("GRIT_ROOT", "~/.grit"))
    )
    ap.add_argument("--host", default=os.environ.get("GRIT_HOST", "127.0.0.1"))
    ap.add_argument(
        "--daemon",
        action="store_true",
        help="detach and keep running after this shell exits",
    )
    ap.add_argument(
        "--stop",
        action="store_true",
        help="stop the daemon named in <root>/daemon.json",
    )
    args = ap.parse_args()

    where = os.path.join(os.path.expanduser(args.root), "daemon.json")

    if args.stop:
        return _stop_daemon(where, args.root)

    if args.daemon:
        return _spawn_daemon(args, where)

    return _serve_foreground(args, where)


def _stop_daemon(where: str, root: str) -> int:
    """Stop the daemon named in <root>/daemon.json."""
    try:
        with open(where, encoding="utf-8") as fh:
            pid = json.load(fh)["pid"]
        os.kill(pid, signal.SIGTERM)
        print("stopped pid %d" % pid)
    except (OSError, ValueError, KeyError):
        print("nothing to stop (no live daemon.json in %s)" % root)
    return 0


def _spawn_daemon(args: argparse.Namespace, where: str) -> int:
    """Detach so the dashboard outlives the shell that started it. Closing a
    terminal should not 404 your own data — that was the single biggest
    day-to-day friction in this product."""
    import subprocess

    proc = subprocess.Popen(
        [
            sys.executable,
            os.path.abspath(__file__),
            "--root",
            args.root,
            "--host",
            args.host,
            "--port",
            str(args.port),
        ],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=open(
            os.path.join(os.path.expanduser(args.root), "daemon.log"), "ab"
        ),
        stderr=subprocess.STDOUT,
    )
    published = _await_publication(where, proc.pid)
    if published is None:
        print(
            "daemon did not start; see %s" % os.path.join(args.root, "daemon.log"),
            file=sys.stderr,
        )
        return 1
    print("grit serve — %s  (detached, pid %d)" % (published["url"], proc.pid))
    return 0


def _await_publication(where: str, pid: int) -> Optional[dict[str, Any]]:
    """Wait for the child to write its address file, then return it.

    Bounded at ~5s: a daemon that has not published by then has failed, and
    waiting forever would hang the installer that called us.
    """
    for _ in range(50):
        time.sleep(0.1)
        try:
            with open(where, encoding="utf-8") as fh:
                info = json.load(fh)
            if info.get("pid") == pid:
                return info
        except (OSError, ValueError):
            pass
    return None




def _serve_foreground(args: argparse.Namespace, where: str) -> int:
    """Bind, publish our address, and serve until interrupted."""
    os.makedirs(args.root, exist_ok=True)
    Handler.state = State(args.root)
    server = _bind(args)
    if server is None:
        return 1
    url = _publish_address(args, server, where)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print("grit serve — %s  (root: %s)" % (url, args.root))
    print("ledger: %s" % Handler.state.ledger_path)
    print("address published to: %s" % where)
    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        print("\nstopped")
    finally:
        _remove_own_address_file(where)
    return 0


def _bind(args: argparse.Namespace) -> Optional[ThreadingHTTPServer]:
    """Bind the socket, or explain how to fix a taken port."""
    try:
        return ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        sys.stderr.write(
            "grit: cannot bind %s:%s — %s\n"
            "      Something else is using that port. Try:\n"
            "        python3 %s --port 0      (any free port)\n"
            "        GRIT_PORT=7802 python3 %s\n"
            % (args.host, args.port, exc.strerror or exc, sys.argv[0], sys.argv[0])
        )
        return None


def _publish_address(
    args: argparse.Namespace, server: ThreadingHTTPServer, where: str
) -> str:
    """Write where we are, so nothing downstream has to assume a port. The
    assistant, the dashboard link and the judge command all read this instead
    of hard-coding 7801 — which was wrong the moment anyone passed --port.

    NOTE: a SIGKILL (or a power cut) leaves this file behind pointing at a dead
    port. Readers should treat it as a hint, not a promise — a failed
    connection means "start the daemon", not "the daemon is broken".
    """
    # --port 0 means the kernel chose; ask the socket what we actually got.
    url = "http://%s:%d" % (args.host, _get_port_of(server))
    with open(where, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "url": url,
                "host": args.host,
                "port": _get_port_of(server),
                "pid": os.getpid(),
                "root": args.root,
                "started": _get_timestamp(),
            },
            fh,
            indent=2,
        )
    return url


def _remove_own_address_file(where: str) -> None:
    """A stale address file sends the next reader to a dead port. Only remove it
    if it is still ours — another daemon may have replaced it."""
    try:
        with open(where, encoding="utf-8") as fh:
            if json.load(fh).get("pid") == os.getpid():
                os.remove(where)
    except (OSError, ValueError):
        pass


class Handler(BaseHTTPRequestHandler):
    state: State = None  # type: ignore[assignment]  # injected before serving

    server_version = "grit/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[grit] " + (fmt % args) + "\n")

    def _send_html(self, code: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_dashboard(self) -> str:
        """The dashboard is a static file next to this daemon, not a Python
        f-string. It is the product's face and it changes often; templating it
        in here meant every colour tweak risked a server-side syntax error."""
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "dashboard.html"
        )
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return (
                "<h1>grit</h1><p>dashboard.html is missing from "
                + _html_escape(os.path.dirname(path))
                + "</p>"
            )

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Closed on purpose. Every client is a page this daemon served (same origin,
    # no header needed) or the assistant's CLI (not a browser). Allowing
    # `localhost:*` is not a boundary on a dev machine — any `npm run dev` in any
    # cloned repo gets one, and /ledger carries every concept you failed.
    def _cors(self) -> None:
        self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")

    def _send_json(self, code: int, obj: Any) -> None:
        body = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        """Route a read request.

        A table, not an if-chain: every route is one line here, and each
        handler is small enough to read on its own. Adding a route means adding
        a row, not widening a branch.
        """
        path = self.path.split("?")[0]
        routes: dict[str, Callable[[], None]] = {
            "/": self._serve_dashboard,
            "/index.html": self._serve_dashboard,
            "/health": self._serve_health,
            "/preferences": self._serve_preferences,
            "/score": self._serve_score,
            "/profile": self._serve_score,  # alias; score.py owns the profile
            "/status": self._serve_status,
            "/authorship": self._serve_authorship,
            "/themes": self._serve_themes,
            "/tutorials": self._serve_tutorial_list,
            "/ledger": self._serve_ledger,
        }
        handler = routes.get(path)
        if handler is not None:
            return handler()
        if path.startswith("/tutorial/"):
            return self._serve_tutorial_file()
        return self._send_json(404, {"error": "not found"})

    def _serve_dashboard(self) -> None:
        self._send_html(200, self._read_dashboard())

    def _serve_health(self) -> None:
        self._send_json(200, {"ok": True, "root": self.state.root})

    def _serve_preferences(self) -> None:
        self._send_json(200, self.state.load_prefs())

    def _serve_score(self) -> None:
        """`/score` and `/profile` share this. Kept as an alias so nothing that
        already points at `/profile` breaks; there is one profile now, and
        score.py owns it (ADR 0009)."""
        self._send_json(200, _score_profile(self.state.root))

    def _serve_authorship(self) -> None:
        self._send_json(200, self.state.authorship())

    def _serve_themes(self) -> None:
        self._send_json(200, {"themes": list(THEMES)})

    def _serve_ledger(self) -> None:
        with self.state.lock:
            self._send_json(200, self.state.ledger)

    def _serve_status(self) -> None:
        """One request instead of several shell round-trips. What is wired up,
        what has been recorded, and what is not built — the three things an
        explicit `/grit` has to answer."""
        return self._send_json(
            200,
            {
                "score": _score_profile(self.state.root),
                "daemon": {
                    "url": "http://%s:%d"
                    % (_get_host_of(self.server), _get_port_of(self.server)),
                    "root": self.state.root,
                },
                "authorship": self.state.authorship(),
                "notices": _compose_config_notices(
                    self.state.root, self.state.load_prefs()
                ),
                "built": {
                    "authorship_hook": True,
                    "dashboard": True,
                    "tutorial_runtime": True,
                },
                "not_built": ["tutorial automation"],
                "note": (
                    "Both evidence sources work. Tutorials are written on "
                    "demand, one concept at a time — there is no library "
                    "and nothing pre-made, so most scores come from real "
                    "repository tasks."
                ),
            },
        )

    def _serve_tutorial_list(self) -> None:
        with self.state.lock:
            names = sorted(
                f
                for f in os.listdir(self.state.tutorials_dir)
                if f.endswith(".html")
            )
            entries = list(self.state.ledger.get("entries", []))
        return self._send_json(
            200,
            {
                "tutorials": [
                    {"name": n, **self.state.summarise_tutorial(n, entries)}
                    for n in names
                ]
            },
        )

    def _resolve_tutorial_path(self) -> Optional[str]:
        """Resolve `/tutorial/<name>` to a real file inside tutorials_dir, or
        None. The `abspath` prefix test is what stops `../` escaping the
        directory — a name is untrusted input from the URL."""
        name = os.path.basename(self.path[len("/tutorial/") :].split("?")[0])
        path = os.path.join(self.state.tutorials_dir, name)
        if not os.path.exists(path):
            return None
        if not os.path.abspath(path).startswith(os.path.abspath(self.state.tutorials_dir)):
            return None
        return path

    def _serve_tutorial_file(self) -> None:
        """Serve a tutorial by name, injecting a fresh session token."""
        path = self._resolve_tutorial_path()
        if path is None:
            return self._send_json(404, {"error": "no such tutorial"})
        html = self._launch_session(path)
        self._write_html(200, html)

    def _launch_session(self, path: str) -> str:
        """Open a session for this tutorial and return its HTML with the report
        token injected. The judge token goes to the operator's terminal and
        never to the browser — that split is what makes gate 3 the assistant's.
        """
        name = os.path.basename(path)
        # Concept identity is NOT the filename (ADR 0009). Prefer the sidecar
        # `<file>.meta.json` — `x.html` -> `x.html.meta.json` — holding
        # {"concept": "token-bucket", "via": "..."}; fall back to the stem so
        # hand-copied tutorials still work.
        concept, via = self.state.resolve_concept(name)
        token, judge_token = self.state.open_session(concept, path, routing_via=via)
        base = "http://%s:%d" % (_get_host_of(self.server), _get_port_of(self.server))
        self._print_judge_command(concept, base, judge_token)
        with open(path, "r", encoding="utf-8") as fh:
            html = fh.read()
        # Hand the page its REPORT token without touching the file on disk.
        return html.replace(
            "</head>",
            "<script>window.GRIT_SESSION="
            + json.dumps(token)
            + ";window.GRIT_DAEMON="
            + json.dumps(base)
            + ";</script></head>",
            1,
        )

    def _print_judge_command(self, concept: str, base: str, judge_token: str) -> None:
        sys.stderr.write(
            "[grit] session for '%s' — judge with:\n"
            "       curl -s -X POST %s/judgment/%s "
            "-H 'Content-Type: application/json' "
            '-d \'{"judgment":"sound"}\'\n' % (concept, base, judge_token)
        )

    def _write_html(self, code: int, html: str) -> None:
        """Write a response we built by hand rather than through `_send_html`,
        which is for static files."""
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        """Route a write request. Each branch is one named handler."""
        payload = self._read_json_body()
        if payload is None:
            return self._send_json(400, {"error": "bad json"})

        parts = [p for p in self.path.split("/") if p]

        # /preferences — the dashboard's only write. Onboarding lands here.
        if parts == ["preferences"]:
            return self._send_json(200, self.state.save_prefs(payload))

        # /judgment/<judge-token> — gate 3, on a SEPARATE path and a separate
        # credential. Never reachable with the token the page holds.
        if len(parts) == 2 and parts[0] == "judgment":
            return self._post_judgment(parts[1], payload)

        # /tutorial/<report-token>/<event> — the two gates the page may report.
        if len(parts) == 3 and parts[0] == "tutorial":
            return self._post_tutorial_gate(parts[1], parts[2], payload)

        return self._send_json(404, {"error": "not found"})

    def _read_json_body(self) -> Optional[dict[str, Any]]:
        """The request body as a dict, or None when it is not valid JSON."""
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, ValueError):
            return None

    def _post_judgment(self, judge_token: str, payload: dict[str, Any]) -> None:
        """Gate 3. The verdict is append-only: the first one stands forever."""
        entry, err = self.state.judge(
            judge_token,
            payload.get("judgment") or "",
            payload.get("message", ""),
        )
        if err:
            return self._refuse_judgment(err, entry)
        if entry is None:  # pragma: no cover — judge() returns one or the other
            return self._send_json(500, {"error": "judged but no row produced"})
        return self._send_json(
            200,
            {
                "ok": True,
                "earned": entry.get("earned"),
                "judgment": entry.get("judgment"),
            },
        )

    def _refuse_judgment(
        self, err: str, entry: Optional[dict[str, Any]]
    ) -> None:
        """An amendment is not a failure to understand — it is a deliberate
        refusal to rewrite. Hand back the standing verdict and the full history
        so the caller sees exactly what holds, rather than a bare error it
        might retry blindly."""
        if err.startswith("already-judged:") and entry:
            return self._send_json(
                409,
                {
                    "error": err,
                    "standing": entry.get("judgment"),
                    "standing_message": entry.get("judgment_message", ""),
                    "earned": entry.get("earned"),
                    "judgments": entry.get("judgments", []),
                    "remedy": (
                        "Gate 3 is append-only. To change the "
                        "outcome, redo the tutorial — that opens a "
                        "new session and produces new evidence."
                    ),
                },
            )
        return self._send_json(400, {"error": err})

    def _post_tutorial_gate(
        self, report_token: str, event: str, payload: dict[str, Any]
    ) -> None:
        """The two gates the page may report: check and justification."""
        if event == "judgment":
            # The page asking to judge itself is the attack this split exists
            # to stop. Refuse loudly rather than 404.
            return self._send_json(
                403,
                {
                    "error": "judgment-requires-judge-token",
                    "detail": "gate 3 is the assistant's; the page cannot award it",
                },
            )
        if event not in ("check", "justification"):
            return self._send_json(404, {"error": "unknown event " + event})

        entry, err = self.state.record(report_token, event, payload)
        if err:
            return self._send_json(400, {"error": err})
        if entry is None:  # pragma: no cover — record() returns one or the other
            return self._send_json(500, {"error": "gate recorded but no row produced"})
        return self._send_json(
            200,
            {
                "ok": True,
                "judgment": entry.get("judgment", "pending"),
                "message": entry.get("judgment_message", ""),
                "earned": entry.get("earned", False),
                "gates_present": entry.get("gates_present", []),
                "gates_required": entry.get("gates_required", list(GATES)),
            },
        )


class State:
    """Sessions and ledger. Single lock; this is a single-user local process."""

    def __init__(self, root: str) -> None:
        self.root = root
        self.lock = threading.Lock()
        # Keyed on the raw tokens, in memory only. Never persisted to the
        # ledger: /ledger is readable, and a token in a readable row is a
        # credential handed to every reader.
        self.sessions: dict[str, Session] = {}  # report token -> Session
        self.judge_index: dict[str, str] = {}  # judge token -> report token
        self.ledger_path = os.path.join(root, "ledger.json")
        self.sessions_path = os.path.join(root, "sessions.json")
        self.prefs_path = os.path.join(root, "preferences.json")
        self.tutorials_dir = os.path.join(root, "tutorials")
        os.makedirs(self.tutorials_dir, exist_ok=True)
        self.ledger: dict[str, Any] = self._load_ledger()
        self._load_sessions()

    def _load_ledger(self) -> dict[str, Any]:
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                # A corrupt ledger is a real event. Do not silently discard it.
                backup = self.ledger_path + ".corrupt-" + _format_stamp()
                try:
                    os.rename(self.ledger_path, backup)
                except OSError:
                    pass
                return {
                    "version": 1,
                    "entries": [],
                    "note": "previous ledger was unreadable; backed up to " + backup,
                }
        return {"version": 1, "entries": []}

    def save_ledger(self) -> None:
        write_send_json(self.ledger_path, self.ledger)

    # ── Sessions survive a restart ───────────────────────────────────────────
    # Gate 3 is the assistant's verdict and may land minutes or hours after the
    # justification. In-memory-only sessions meant any restart in that window
    # stranded the concept permanently unearned, with no route to fix it except
    # hand-editing the ledger — which ADR 0006 forbids.
    def _load_sessions(self) -> None:
        if not os.path.exists(self.sessions_path):
            return
        try:
            with open(self.sessions_path, "r", encoding="utf-8") as fh:
                blob = json.load(fh)
            self.sessions = {
                tok: Session.from_dict(raw)
                for tok, raw in (blob.get("sessions") or {}).items()
            }
            self.judge_index = blob.get("judge_index", {})
        except (json.JSONDecodeError, OSError):
            self.sessions, self.judge_index = {}, {}

    def _save_sessions(self) -> None:
        """Caller holds the lock. Mode 0600: this file holds live credentials."""
        write_send_json(
            self.sessions_path,
            {
                "sessions": {t: s.to_dict() for t, s in self.sessions.items()},
                "judge_index": self.judge_index,
            },
            mode=0o600,
        )

    # ── Preferences ──────────────────────────────────────────────────────────
    def load_prefs(self) -> dict[str, Any]:
        if os.path.exists(self.prefs_path):
            try:
                with open(self.prefs_path, "r", encoding="utf-8") as fh:
                    return {**DEFAULT_PREFS, **json.load(fh)}
            except (json.JSONDecodeError, OSError):
                pass
        return dict(DEFAULT_PREFS)

    def save_prefs(self, patch: Optional[dict[str, Any]]) -> dict[str, Any]:
        prefs = self.load_prefs()
        for key, value in (patch or {}).items():
            if key in DEFAULT_PREFS:  # ignore unknown keys, don't 400
                prefs[key] = value
        if prefs.get("theme") not in THEMES:
            prefs["theme"] = DEFAULT_PREFS["theme"]
        write_send_json(self.prefs_path, prefs)
        return prefs

    def open_session(
        self, concept: str, tutorial: str, routing_via: Optional[str] = None
    ) -> tuple[str, str]:
        """Open a tutorial session. Returns (report_token, judge_token).

        `concept` is the concept's identity (e.g. "token-bucket"), NOT a
        filename. `tutorial` is the file it came from. Keeping them separate is
        what lets the profile aggregate evidence per concept (ADR 0009); keying
        on the filename made two tutorials about one idea into two unrelated
        rows.

        TWO tokens, and this is the whole point of the daemon. The *report*
        token is injected into the page, and buys only `check` and
        `justification` — the two gates the page legitimately observes. The
        *judge* token never reaches the browser; it is printed to the daemon's
        stdout for the assistant. With one shared token the page could POST its
        own judgment and award itself the third gate, which made ADR 0005's
        guarantee — "the page never writes the ledger" — true in letter and
        worthless in fact.
        """
        report_token = secrets.token_urlsafe(24)
        judge_token = secrets.token_urlsafe(24)
        with self.lock:
            self.sessions[report_token] = self._build_session(
                concept, tutorial, routing_via
            )
            self.judge_index[judge_token] = report_token
            self._save_sessions()
        return report_token, judge_token

    def _build_session(
        self, concept: str, tutorial: str, routing_via: Optional[str]
    ) -> Session:
        return Session(
            # A short public row id. The raw tokens must never enter the ledger:
            # /ledger is readable, and a token in a readable row is a credential
            # handed to every reader.
            sid=secrets.token_hex(8),
            concept=concept,
            tutorial=tutorial,
            opened=_get_timestamp(),
            gates={},  # gate -> payload
            judgment="pending",
            # Why this tutorial fired. Without it the ADR 0012 audit cannot tell
            # whether the battery is the thing mis-routing.
            routing_via=routing_via or "unknown",
            reports=[],
        )

    def get_session(self, token: str) -> Optional[Session]:
        with self.lock:
            return self.sessions.get(token)

    def record(
        self, token: str, gate: str, payload: dict[str, Any]
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Record one gate. Returns (entry, error)."""
        with self.lock:
            session = self.sessions.get(token)
            if session is None:
                return None, "unknown-session"
            verification, err = self._apply_gate(session, gate, payload)
            if err:
                return None, err
            session.reports.append({"gate": gate, "at": _get_timestamp()})
            return self._commit(session, verification), None

    def _apply_gate(
        self, session: Session, gate: str, payload: dict[str, Any]
    ) -> tuple[str, Optional[str]]:
        """Write one gate onto the session. Returns (verification, error), with
        exactly one of the two meaningful."""
        if gate == "check":
            session.gates["check"] = CheckGate(
                passed=bool(payload.get("passed")),
                message=payload.get("message", ""),
                at=_get_timestamp(),
            ).to_dict()
            return "verified-by-execution", None
        if gate == "justification":
            if not session.gates.get("check", {}).get("passed"):
                # A justification without a passed check is out of order.
                return "", "check-not-passed"
            session.gates["justification"] = JustificationGate(
                answer=(payload.get("answer") or "").strip(),
                at=_get_timestamp(),
            ).to_dict()
            return "awaiting-judgment", None
        return "", "unknown-gate:" + gate

    def _commit(self, session: Session, verification: str) -> dict[str, Any]:
        """Write this session's single ledger row. Caller holds the lock."""
        entry = self._build_entry(session, verification)
        self._upsert_ledger_entry(entry, session)
        self._score_once_if_final(session, entry)
        return entry

    def _build_entry(self, session: Session, verification: str) -> dict[str, Any]:
        entry = self._get_entry_for(session)
        entry["verification"] = verification
        entry["gates_present"] = sorted(session.gates.keys())
        entry["gates_required"] = list(GATES)
        entry["earned"] = _is_earned(session)
        return entry

    def _upsert_ledger_entry(self, entry: dict[str, Any], session: Session) -> None:
        """Append-or-replace by row id, so re-reporting a gate updates rather
        than duplicating history."""
        self.ledger["entries"] = [
            e for e in self.ledger["entries"] if e.get("session") != session.sid
        ]
        self.ledger["entries"].append(entry)
        self.save_ledger()
        self._save_sessions()

    def _score_once_if_final(self, session: Session, entry: dict[str, Any]) -> None:
        """The bridge the two halves were missing: a tutorial that passes all
        three gates becomes SANDBOX evidence, so completing one actually moves a
        score. Keyed on the tutorial so repeating the same exercise decays under
        the novelty rule (ADR 0009) instead of paying forever.

        Unsound records a failure, not silence — the score model counts failures
        (ADR 0009), so an unrecorded one reads as "never attempted"."""
        if session.scored:
            return
        task = os.path.basename(session.tutorial)
        if entry["earned"]:
            session.scored = True
            self._record_evidence(session.concept, task)
            return
        if session.gates.get("judgment", {}).get("judgment") == "unsound":
            session.scored = True
            self._record_evidence(session.concept, task, failed=True)

    def _record_evidence(
        self, concept: str, task: str, failed: bool = False
    ) -> None:
        """Write one sandbox evidence row. Never let a scoring failure cost the
        user a completed tutorial — the ledger entry is already committed."""
        try:
            # No project: a tutorial is the same exercise wherever it is run,
            # so repeating it must decay regardless of which repo you are in.
            _import_sibling("score").record(
                self.root,
                concept,
                "sandbox",
                "none",
                task,
                detail=(
                    "justification judged unsound"
                    if failed
                    else "tutorial completed, all three gates"
                ),
                failed=failed,
            )
        except Exception as exc:
            sys.stderr.write("[grit] could not score %s: %s\n" % (concept, exc))

    def judge(
        self, judge_token: str, judgment: str, message: str = ""
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Gate 3 — the assistant's verdict on the justification text.

        Takes the JUDGE token, which the page never receives. A judgment is a
        model output and must not be reachable from anything the page holds.
        """
        if judgment not in JUDGMENTS:
            return None, "bad-judgment:" + str(judgment)
        with self.lock:
            session = self._session_for_judge_token(judge_token)
            if isinstance(session, str):  # an error message, not a session
                return None, session
            return self._cast_verdict(session, judgment, message)

    def _session_for_judge_token(self, judge_token: str) -> Any:
        """The session a judge token unlocks, or an error string."""
        report_token = self.judge_index.get(judge_token)
        session = self.sessions.get(report_token) if report_token else None
        if session is None:
            return "unknown-session"
        if "justification" not in session.gates:
            return "justification-not-submitted"
        return session

    def _cast_verdict(
        self, session: Session, judgment: str, message: str
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Append this verdict, or treat it as an amendment if one already
        stands.

        Append-only: the first verdict stands, later ones are amendments that
        change nothing. The remedy for a wrong verdict is a fresh attempt, not
        an edit (ADR 0006).
        """
        stamped = Judgment(
            judgment=cast(JudgmentVerdict, judgment), message=message, at=_get_timestamp()
        ).to_dict()
        session.judgments.append(stamped)
        if len(session.judgments) > 1:
            return self._record_amendment(session)
        return self._record_first_verdict(session, stamped), None

    def _record_amendment(
        self, session: Session
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """A later verdict is kept for audit and changes nothing."""
        first = session.judgments[0]
        self._save_sessions()
        amended = self._get_entry_for(session)
        # Derive it here too: `_get_entry_for` does not set `earned` (only `_commit`
        # does), and an amendment must never be ambiguous about what currently
        # holds.
        amended["earned"] = _is_earned(session)
        return amended, (
            "already-judged:%s (amendment #%d recorded; the first "
            "verdict stands and the score is unchanged)"
            % (first["judgment"], len(session.judgments) - 1)
        )

    def _record_first_verdict(
        self, session: Session, stamped: dict[str, str]
    ) -> dict[str, Any]:
        """The standing verdict. It IS the third gate, so it goes in `gates`
        too — otherwise the gate list contradicts `earned`, which is exactly the
        kind of inconsistency this ledger exists to prevent."""
        session.judgment = stamped["judgment"]  # type: ignore[assignment]
        session.judgment_message = stamped["message"]
        session.judgment_at = stamped["at"]
        session.gates["judgment"] = dict(stamped)
        return self._commit(session, "judged-" + stamped["judgment"])

    def _get_entry_for(self, session: Session) -> dict[str, Any]:
        return {
            "session": session.sid,
            "concept": session.concept,
            "tutorial": session.tutorial,
            "opened": session.opened,
            "routing_via": session.routing_via,
            "judgment": session.judgment,
            "judgment_message": session.judgment_message,
            # Every verdict ever cast on this session, in order. The first one
            # is the one in effect; the rest are amendments kept for audit.
            "judgments": list(session.judgments),
            "gates": session.gates,
        }

    def summarise_tutorial(
        self, name: str, entries: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Summarise a tutorial's most recent attempt. Newest wins, because a
        user who retried and passed should not be shown a stale failure.

        `name` is the bare filename the route serves; the ledger stores the
        full path the session was opened against. Compare on basenames, or
        nothing ever matches and every tutorial reads "not started".
        """
        for entry in reversed(entries):
            if os.path.basename(entry.get("tutorial", "")) == name:
                return self._summarise_attempt(entry)
        return {"status": "not started", "detail": "no attempts recorded"}

    def _summarise_attempt(self, entry: dict[str, Any]) -> dict[str, str]:
        """Turn one ledger row into a status line.

        The order of these checks is the meaning. `pending` must be tested
        before `missing`, because a pending judgment has no `judgment` gate
        yet — checking missing first makes "awaiting judgment" unreachable and
        reports an outstanding verdict as incomplete.
        """
        if entry.get("earned", False):
            return {"status": "earned", "detail": "all three gates"}
        gates = entry.get("gates", {})
        if not gates.get("check", {}).get("passed", False):
            return {"status": "unearned", "detail": self._why_check_failed(gates)}
        judgment = entry.get("judgment", "pending")
        if judgment == "unsound":
            # Judged and rejected. Saying "awaiting judgment" here would tell a
            # user their failed attempt is still in progress.
            return {"status": "unearned", "detail": self._why_unsound(entry)}
        if judgment == "pending":
            return {"status": "unearned", "detail": self._awaiting_judgment(entry)}
        missing = [g for g in GATES if g not in gates]
        if missing:
            return {"status": "unearned", "detail": "missing: " + ", ".join(missing)}
        return {"status": "unearned", "detail": "incomplete"}

    def _why_check_failed(self, gates: dict[str, Any]) -> str:
        if not gates.get("check"):
            return "check not passed"
        return "check not passed: " + gates["check"].get("message", "")

    def _why_unsound(self, entry: dict[str, Any]) -> str:
        if not entry.get("judgment_message"):
            return "justification judged unsound"
        return "justification judged unsound: " + entry["judgment_message"]

    def _awaiting_judgment(self, entry: dict[str, Any]) -> str:
        """Say how long it has been waiting.

        A verdict that never arrives is otherwise indistinguishable from one
        still in flight, and the user has no signal that the assistant still
        owes them a judgment. Age is the only honest way to show that.
        """
        opened = _parse_iso(entry.get("opened") or entry.get("at"))
        if opened is None:
            return "awaiting judgment"
        hours = (datetime.now(timezone.utc) - opened).total_seconds() / 3600.0
        if hours < 1:
            return "awaiting judgment"
        return "awaiting judgment for %s" % (
            "%dh" % int(hours) if hours < 48 else "%dd" % int(hours // 24)
        )

    # ── Authorship: the measurement that works without a tutorial ────────────
    def authorship(self) -> dict[str, Any]:
        """Aggregate every project's authorship log.

        Reports ONLY what was observed: lines the assistant wrote, and shell
        calls whose effect nobody watched. It deliberately does not compute a
        percentage — the human side is not observed at all, so any denominator
        here would be invented. `verify_edit.py` gets a real one per task, from
        git; this view does not pretend to.
        """
        try:
            with open(os.path.join(self.root, "projects.json"), encoding="utf-8") as fh:
                projects = json.load(fh)
        except (OSError, ValueError):
            projects = []

        out = [
            summary
            for summary in (self._read_project_log(p) for p in projects)
            if summary is not None
        ]
        totals = {"lines": 0, "edits": 0, "shell": 0, "offers": 0, "taken": 0}
        for summary in out:
            for k in ("lines", "edits", "shell", "offers", "taken"):
                totals[k] += summary[k]
        out.sort(key=lambda p: p["last"], reverse=True)
        return {
            "projects": out,
            "totals": totals,
            "hook_active": _is_hook_active(),
            "note": (
                "Assistant-authored only. Your own edits are not "
                "observed, so there is no percentage here to report."
            ),
        }

    def _read_project_log(self, path: str) -> Optional[dict[str, Any]]:
        """One project's authorship summary, or None when it has no log."""
        log = os.path.join(_get_project_dir(self.root, path), "authorship.jsonl")
        if not os.path.exists(log):
            return None
        summary = ProjectAuthorship(project=path)
        offer_sessions: set[str] = set()
        edit_sessions: set[str] = set()
        try:
            with open(log, encoding="utf-8") as fh:
                for raw in fh:
                    self._tally_row(summary, raw, offer_sessions, edit_sessions)
        except OSError:
            return None
        # Sessions where the choice was offered and no assistant edit followed:
        # the only evidence we have that anyone took it.
        summary.taken = len(offer_sessions - edit_sessions)
        return summary.to_dict()

    def _tally_row(
        self,
        summary: ProjectAuthorship,
        raw: str,
        offer_sessions: set[str],
        edit_sessions: set[str],
    ) -> None:
        """Fold one log line into the running summary. A malformed line is
        skipped, never fatal — one bad row must not void a project's record."""
        try:
            row = json.loads(raw)
        except ValueError:
            return
        summary.last = max(summary.last, row.get("at", ""))
        if row.get("event") == "offered":
            summary.offers += 1
            offer_sessions.add(row.get("session", ""))
            return
        if row.get("author") != "assistant":
            return
        edit_sessions.add(row.get("session", ""))
        if row.get("opaque"):
            summary.shell += 1
            return
        summary.edits += 1
        summary.lines += int(row.get("lines") or 0)
        if row.get("file"):
            summary.files.add(row["file"])

    def resolve_concept(self, tutorial_name: str) -> tuple[str, str]:
        """Resolve (concept, routing_via) for a tutorial file.

        Concept identity must not be the filename (ADR 0009) — two tutorials
        about one idea would otherwise be unrelated rows. A sidecar named for
        the tutorial file plus `.meta.json` (so `token-bucket.html` pairs with
        `token-bucket.html.meta.json`) supplies both; without one, the stem is
        used as a best guess and provenance is recorded as unknown.
        """
        sidecar = os.path.join(self.tutorials_dir, tutorial_name + ".meta.json")
        if os.path.exists(sidecar):
            try:
                with open(sidecar, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
                concept = meta.get("concept") or os.path.splitext(tutorial_name)[0]
                return concept, meta.get("via", "unknown")
            except (json.JSONDecodeError, OSError):
                pass
        return os.path.splitext(tutorial_name)[0], "unknown"


@dataclass(frozen=True)
class Judgment:
    """One verdict. Append-only: `session["judgments"]` keeps every one ever
    cast, and the first entry is the one in effect (ADR 0006)."""

    judgment: JudgmentVerdict
    message: str = ""
    at: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"judgment": self.judgment, "message": self.message, "at": self.at}




@dataclass(frozen=True)
class CheckGate:
    """Gate 1. `check_type` is always "sandbox" — ADR 0004 forbids a repo check
    here, and the field exists so the ledger says which oracle produced this."""

    passed: bool
    message: str = ""
    at: str = ""
    check_type: Literal["sandbox"] = "sandbox"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "check_type": self.check_type,
            "message": self.message,
            "at": self.at,
        }




@dataclass(frozen=True)
class JustificationGate:
    """Gate 2. The free-text answer gate 3 judges."""

    answer: str
    at: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"answer": self.answer, "at": self.at}




@dataclass
class Session:
    """One tutorial launch. Held in memory AND persisted to sessions.json at
    mode 0600 — gate 3 may land minutes or hours after gate 2, so a restart in
    that window must not strand the concept (ADR 0006).

    Mutable on purpose: gates arrive over time. `earned` is deliberately NOT a
    field here — it is derived by `_is_earned()` from the gate dict, so no stored
    copy can contradict the gates it claims to summarise.
    """

    sid: str
    concept: str
    tutorial: str
    opened: str
    gates: dict[str, dict[str, Any]] = field(default_factory=dict)
    judgment: JudgmentVerdict = "pending"
    judgment_message: str = ""
    judgment_at: str = ""
    routing_via: str = "unknown"
    reports: list[dict[str, str]] = field(default_factory=list)
    judgments: list[dict[str, str]] = field(default_factory=list)
    scored: bool = False

    # Unlike the gate dataclasses, sessions.json IS the storage format: the
    # daemon writes this dict and reloads it verbatim on restart, so the shape
    # has to round-trip unchanged.
    def to_dict(self) -> dict[str, Any]:
        return {
            "sid": self.sid,
            "concept": self.concept,
            "tutorial": self.tutorial,
            "opened": self.opened,
            "gates": self.gates,
            "judgment": self.judgment,
            "judgment_message": self.judgment_message,
            "judgment_at": self.judgment_at,
            "routing_via": self.routing_via,
            "reports": self.reports,
            "judgments": self.judgments,
            "scored": self.scored,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Session":
        """Reload a persisted session. Tolerant of a row written by an older
        version, which is why every field has a default."""
        return cls(
            sid=str(raw.get("sid", "")),
            concept=str(raw.get("concept", "")),
            tutorial=str(raw.get("tutorial", "")),
            opened=str(raw.get("opened", "")),
            gates=raw.get("gates", {}),
            judgment=raw.get("judgment", "pending"),
            judgment_message=str(raw.get("judgment_message", "")),
            judgment_at=str(raw.get("judgment_at", "")),
            routing_via=str(raw.get("routing_via", "unknown")),
            reports=raw.get("reports", []),
            judgments=raw.get("judgments", []),
            scored=bool(raw.get("scored", False)),
        )




@dataclass
class ProjectAuthorship:
    """One project's authorship tallies, read from its `projects/<key>/authorship.jsonl`
    under the daemon root.

    `offers` counts sessions where the choice was put to the user; `taken`
    counts sessions where it was offered and no assistant edit followed — the
    only evidence this product has that anyone took it.
    """

    project: str
    lines: int = 0
    edits: int = 0
    shell: int = 0
    files: set[str] = field(default_factory=set)
    last: str = ""
    offers: int = 0
    taken: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "lines": self.lines,
            "edits": self.edits,
            "shell": self.shell,
            "files": len(self.files),
            "last": self.last,
            "offers": self.offers,
            "taken": self.taken,
            "recent": sorted(self.files)[-5:],
        }


def _is_earned(session: Session) -> bool:
    """The one definition of earned: all three gates present, the check still
    passing, the judgment sound.

    Derived here and nowhere else, so two code paths cannot disagree about what
    the word means.
    """
    gates = session.gates
    if not all(g in gates for g in GATES):
        return False
    if not gates.get("check", {}).get("passed"):
        return False
    return gates.get("judgment", {}).get("judgment") == "sound"


def _compose_config_notices(root: str, prefs: dict[str, Any]) -> list[dict[str, str]]:
    """What the product is doing to itself — never what a session did.

    Two rules meet here and used to look like they contradicted each other.
    Opting out of a task records nothing about that task, and that stays true:
    measuring someone who declined is surveillance. But a *standing setting*
    that disables the only function this product has is not a session, and
    leaving it unsaid is the METR pattern — feeling fine while capability
    erodes with nothing on screen to disagree. So the setting is shown, and
    the outcomes under it are shown as counts. Nothing here overrules a
    preference; a correction the user cannot see applied is applied by stealth.

    `visible_overrides` used to be a preferences key for this and was never
    written or read by anything. A stored list would be a second place the
    answer lives, which is the defect `earned` exists not to have.
    """
    notices: list[dict[str, str]] = []
    if prefs.get("default_do_it_myself") is False:
        notices.append(
            {
                "kind": "mechanism-off",
                "text": (
                    "Your default is to hand work straight over. Nothing is "
                    "being offered, and nothing is being scored."
                ),
            }
        )
    try:
        rows = _import_sibling("score").load(root)
    except Exception:
        return notices  # scoring unavailable is already reported elsewhere
    walked = [r for r in rows if r.assistance == "partial"]
    missed = [r for r in walked if r.failed]
    if missed:
        notices.append(
            {
                "kind": "preference-vs-outcome",
                "text": (
                    "%d of your %d walked-through attempts did not pass. "
                    "Walking through it may not be working for you — the "
                    "counts are here; the choice stays yours."
                )
                % (len(missed), len(walked)),
            }
        )
    return notices


def _score_profile(root: str) -> dict[str, Any]:
    """Per-concept levels from evidence.jsonl. Imported lazily and defensively:
    the dashboard must still render if scoring is missing or broken."""
    try:
        return _import_sibling("score").profile(root).to_dict()
    except Exception as exc:
        return {
            "concepts": {},
            "headline": {"proven": 0, "recall": 0, "tracked": 0},
            "error": "%s: %s" % (type(exc).__name__, exc),
        }


def _import_sibling(name: str) -> ModuleType:
    """Import a module from this skill's own directory.

    The skill ships as a flat folder with no package, so siblings load by path.
    Insert once: callers run per request, and repeating the insert grows
    sys.path without bound.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    return importlib.import_module(name)


def write_send_json(path: str, data: Any, mode: Optional[int] = None) -> None:
    """Write JSON atomically: temp file, then rename.

    Every file here is state a crash must not half-write; a truncated
    ledger.json is unrecoverable.
    """
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, path)


def _get_project_dir(root: str, cwd: str) -> str:
    """Where a project's own state lives under `root` (a person's ~/.grit).
    Mirrors hooks/grit-hook.py's helper of the same name — kept independent
    since the hook has no import path back into this package."""
    key = hashlib.sha256(os.path.realpath(cwd).encode()).hexdigest()[:16]
    return os.path.join(root, "projects", key)


def _is_hook_active() -> Optional[bool]:
    """Is a grit hook actually registered and runnable for this user, right now?

    `doctor.is_watching` already answers this without spawning the hook, so it
    is reused rather than re-derived. `None` (not `False`) on any failure: the
    dashboard must read "unknown" as "unknown", never as "not installed" — a
    false negative here would tell an honestly-hooked user their authorship
    is not being recorded when it is.
    """
    try:
        return bool(_import_sibling("doctor").is_watching(os.path.expanduser("~")))
    except Exception:
        return None


def _get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    """Parse an ISO timestamp, tolerating the 'Z' suffix and naive values.
    Returns None rather than raising — a malformed timestamp should not take
    down profile derivation."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _format_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _get_host_of(server: Any) -> str:
    """The bound host as a string.

    `server_address` is typed as a union (TCP gives a 2-tuple, a Unix socket a
    str) because the base class covers both. We always bind TCP, so narrowing
    here once beats indexing a union at every call site.
    """
    address = server.server_address
    return address[0] if isinstance(address, tuple) else "127.0.0.1"


def _get_port_of(server: Any) -> int:
    """The actually-bound port. `--port 0` means the kernel chose, so the
    answer must come from the socket and never from the requested value."""
    address = server.server_address
    return address[1] if isinstance(address, tuple) else 0


def _html_escape(s: Any) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
