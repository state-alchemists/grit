#!/usr/bin/env python3
"""
grit serve — the local daemon (ADR 0009).

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

import argparse
import json
import os
import secrets
import signal
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ── The three gates (ADR 0009) ───────────────────────────────────────────────
# A concept is earned only when all three hold. Kept explicit so the ordering
# cannot drift as the code changes.
GATES = ("check", "justification", "judgment")

# Verdicts a judgment gate may return. "pending" is not earned.
JUDGMENTS = ("sound", "unsound", "pending")

# Default only. Override with --port or GRIT_PORT; --port 0 takes any free port.
# Whatever is actually bound gets written to <root>/daemon.json, and everything
# downstream reads that rather than assuming this number.
DEFAULT_PORT = int(os.environ.get("GRIT_PORT", 7801))

# ── Dashboard themes (chosen at onboarding) ──────────────────────────────────
# Names only; the palettes live in dashboard.html. Kept here so the daemon can
# reject an unknown theme rather than serve a page with no colours.
THEMES = ("dungeon", "terminal", "synthwave", "forest", "arcade", "paper")

DEFAULT_PREFS = {
    "version": 1,
    "onboarded": False,
    "theme": "dungeon",
    "callsign": "",
    "motion": True,             # animations; off is a real accessibility need
    "ask_on_first_edit": True,  # the PreToolUse hook's one prompt per session
    "format": "socratic",
    "depth": "standard",
    "pace": "one-at-a-time",
    "default_do_it_myself": True,
    "visible_overrides": [],
}


def _earned(session):
    """The ONE definition of earned. Every gate must be present, the check must
    actually have passed, and the judgment must be sound.

    Derived in one place on purpose: this was previously assigned separately in
    `record()` and `judge()`, and the two disagreed — re-reporting a failed
    check after a sound judgment left a row asserting `earned: true` while
    carrying `check.passed: false`.
    """
    gates = session.get("gates", {})
    if not all(g in gates for g in GATES):
        return False
    if not gates.get("check", {}).get("passed"):
        return False
    return gates.get("judgment", {}).get("judgment") == "sound"


class State:
    """Sessions and ledger. Single lock; this is a single-user local process."""

    def __init__(self, root):
        self.root = root
        self.lock = threading.Lock()
        self.sessions = {}          # report token -> session dict
        self.judge_index = {}       # judge token  -> report token
        self.ledger_path = os.path.join(root, "ledger.json")
        self.sessions_path = os.path.join(root, "sessions.json")
        self.prefs_path = os.path.join(root, "preferences.json")
        self.tutorials_dir = os.path.join(root, "tutorials")
        os.makedirs(self.tutorials_dir, exist_ok=True)
        self.ledger = self._load()
        self._load_sessions()

    def _load(self):
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                # A corrupt ledger is a real event. Do not silently discard it.
                backup = self.ledger_path + ".corrupt-" + _stamp()
                try:
                    os.rename(self.ledger_path, backup)
                except OSError:
                    pass
                return {"version": 1, "entries": [],
                        "note": "previous ledger was unreadable; backed up to " + backup}
        return {"version": 1, "entries": []}

    def save(self):
        tmp = self.ledger_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.ledger, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.ledger_path)   # atomic; never a half-written ledger

    # ── Sessions survive a restart ───────────────────────────────────────────
    # Gate 3 is the assistant's verdict and may land minutes or hours after the
    # justification. In-memory-only sessions meant any restart in that window
    # stranded the concept permanently unearned, with no route to fix it except
    # hand-editing the ledger — which ADR 0010 forbids.
    def _load_sessions(self):
        if not os.path.exists(self.sessions_path):
            return
        try:
            with open(self.sessions_path, "r", encoding="utf-8") as fh:
                blob = json.load(fh)
            self.sessions = blob.get("sessions", {})
            self.judge_index = blob.get("judge_index", {})
        except (json.JSONDecodeError, OSError):
            self.sessions, self.judge_index = {}, {}

    def _save_sessions(self):
        """Caller holds the lock. Mode 0600: this file holds live credentials."""
        tmp = self.sessions_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"sessions": self.sessions,
                       "judge_index": self.judge_index}, fh, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.sessions_path)

    # ── Preferences ──────────────────────────────────────────────────────────
    def load_prefs(self):
        if os.path.exists(self.prefs_path):
            try:
                with open(self.prefs_path, "r", encoding="utf-8") as fh:
                    return {**DEFAULT_PREFS, **json.load(fh)}
            except (json.JSONDecodeError, OSError):
                pass
        return dict(DEFAULT_PREFS)

    def save_prefs(self, patch):
        prefs = self.load_prefs()
        for key, value in (patch or {}).items():
            if key in DEFAULT_PREFS:          # ignore unknown keys, don't 400
                prefs[key] = value
        if prefs.get("theme") not in THEMES:
            prefs["theme"] = DEFAULT_PREFS["theme"]
        tmp = self.prefs_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(prefs, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.prefs_path)
        return prefs

    def open_session(self, concept, tutorial, routing_via=None):
        """Open a tutorial session. Returns (report_token, judge_token).

        `concept` is the concept's identity (e.g. "token-bucket"), NOT a
        filename. `tutorial` is the file it came from. Keeping them separate is
        what lets the profile aggregate evidence per concept (ADR 0010); keying
        on the filename made two tutorials about one idea into two unrelated
        rows.

        TWO tokens, and this is the whole point of the daemon. The *report*
        token is injected into the page, and buys only `check` and
        `justification` — the two gates the page legitimately observes. The
        *judge* token never reaches the browser; it is printed to the daemon's
        stdout for the assistant. With one shared token the page could POST its
        own judgment and award itself the third gate, which made ADR 0009's
        guarantee — "the page never writes the ledger" — true in letter and
        worthless in fact.
        """
        report_token = secrets.token_urlsafe(24)
        judge_token = secrets.token_urlsafe(24)
        with self.lock:
            self.sessions[report_token] = {
                # A short public row id. The raw tokens must never enter the
                # ledger: /ledger is readable, and a token in a readable row is
                # a credential handed to every reader.
                "sid": secrets.token_hex(8),
                "concept": concept,
                "tutorial": tutorial,
                "opened": _now(),
                "gates": {},          # gate -> payload
                "judgment": "pending",
                # Why this tutorial fired. Without it the ADR 0007 audit cannot
                # tell whether the battery is the thing mis-routing.
                "routing_via": routing_via or "unknown",
                "reports": [],
            }
            self.judge_index[judge_token] = report_token
            self._save_sessions()
        return report_token, judge_token

    def get_session(self, token):
        with self.lock:
            return self.sessions.get(token)

    def record(self, token, gate, payload):
        """Record one gate. Returns (entry, error)."""
        with self.lock:
            session = self.sessions.get(token)
            if session is None:
                return None, "unknown-session"

            if gate == "check":
                session["gates"]["check"] = {
                    "passed": bool(payload.get("passed")),
                    "check_type": "sandbox",     # ADR 0008: never a repo check
                    "message": payload.get("message", ""),
                    "at": _now(),
                }
                verification = "verified-by-execution"

            elif gate == "justification":
                if not session["gates"].get("check", {}).get("passed"):
                    # A justification without a passed check is out of order.
                    return None, "check-not-passed"
                session["gates"]["justification"] = {
                    "answer": (payload.get("answer") or "").strip(),
                    "at": _now(),
                }
                verification = "awaiting-judgment"

            else:
                return None, "unknown-gate:" + gate

            session["reports"].append({"gate": gate, "at": _now()})
            entry = self._commit(session, verification)
            return entry, None

    def _commit(self, session, verification):
        """Write this session's single ledger row. Caller holds the lock."""
        entry = self._entry_for(session)
        entry["verification"] = verification
        entry["gates_present"] = sorted(session["gates"].keys())
        entry["gates_required"] = list(GATES)
        entry["earned"] = _earned(session)
        # Append-or-replace by row id, so re-reporting a gate updates rather
        # than duplicating history.
        self.ledger["entries"] = [
            e for e in self.ledger["entries"] if e.get("session") != session["sid"]
        ]
        self.ledger["entries"].append(entry)
        self.save()
        self._save_sessions()

        # The bridge the two halves were missing: a tutorial that passes all
        # three gates becomes SANDBOX evidence, so completing one actually
        # moves a score. Keyed on the tutorial so repeating the same exercise
        # decays under the novelty rule (ADR 0014) instead of paying forever.
        if entry["earned"] and not session.get("scored"):
            session["scored"] = True
            self._record_evidence(session["concept"],
                                  os.path.basename(session["tutorial"]))
        return entry

    def _record_evidence(self, concept, task):
        """Write one sandbox evidence row. Never let a scoring failure cost the
        user a completed tutorial — the ledger entry is already committed."""
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import score
            # No project: a tutorial is the same exercise wherever it is run,
            # so repeating it must decay regardless of which repo you are in.
            score.record(self.root, concept, "sandbox", "none", task,
                         detail="tutorial completed, all three gates")
        except Exception as exc:
            sys.stderr.write("[grit] could not score %s: %s\n" % (concept, exc))

    def judge(self, judge_token, judgment, message=""):
        """Gate 3 — the assistant's verdict on the justification text.

        Takes the JUDGE token, which the page never receives. A judgment is a
        model output and must not be reachable from anything the page holds.
        """
        if judgment not in JUDGMENTS:
            return None, "bad-judgment:" + str(judgment)
        with self.lock:
            report_token = self.judge_index.get(judge_token)
            session = self.sessions.get(report_token) if report_token else None
            if session is None:
                return None, "unknown-session"
            if "justification" not in session["gates"]:
                return None, "justification-not-submitted"
            session["judgment"] = judgment
            session["judgment_message"] = message
            session["judgment_at"] = _now()
            # The judgment IS the third gate. Record it in `gates` too, or the
            # gate list contradicts `earned` — which is exactly the kind of
            # inconsistency this ledger exists to prevent.
            session["gates"]["judgment"] = {
                "judgment": judgment,
                "message": message,
                "at": _now(),
            }
            entry = self._commit(session, "judged-" + judgment)
            return entry, None

    def _entry_for(self, session):
        return {
            "session": session["sid"],
            "concept": session["concept"],
            "tutorial": session["tutorial"],
            "opened": session["opened"],
            "routing_via": session.get("routing_via", "unknown"),
            "judgment": session.get("judgment", "pending"),
            "judgment_message": session.get("judgment_message", ""),
            "gates": session["gates"],
        }

    def view_of_tutorial(self, name, entries):
        """Summarise a tutorial's most recent attempt. Newest wins, because a
        user who retried and passed should not be shown a stale failure."""
        for entry in reversed(entries):
            if entry.get("tutorial") != name:
                continue
            earned = entry.get("earned", False)
            gates = entry.get("gates", {})
            present = entry.get("gates_present", sorted(gates.keys()))
            missing = [g for g in GATES if g not in gates]
            if earned:
                return {"status": "earned", "detail": "all three gates"}
            if not gates.get("check", {}).get("passed", False):
                return {"status": "unearned",
                        "detail": "check not passed"
                                  + (": " + entry["gates"]["check"].get("message", "")
                                     if gates.get("check") else "")}
            judgment = entry.get("judgment", "pending")
            if judgment == "unsound":
                # Judged and rejected. Saying "awaiting judgment" here would
                # tell a user their failed attempt is still in progress.
                return {"status": "unearned",
                        "detail": "justification judged unsound"
                                  + (": " + entry["judgment_message"]
                                     if entry.get("judgment_message") else "")}
            missing = [g for g in GATES if g not in gates]
            if missing:
                return {"status": "unearned", "detail": "missing: " + ", ".join(missing)}
            if judgment == "pending":
                return {"status": "unearned", "detail": "awaiting judgment"}
            return {"status": "unearned", "detail": "incomplete"}
        return {"status": "not started", "detail": "no attempts recorded"}

    def concept_of(self, tutorial_name):
        """Resolve (concept, routing_via) for a tutorial file.

        Concept identity must not be the filename (ADR 0010) — two tutorials
        about one idea would otherwise be unrelated rows. A sidecar
        `<name>.meta.json` supplies both; without one, the stem is used as a
        best guess and provenance is recorded as unknown.
        """
        sidecar = os.path.join(self.tutorials_dir,
                               tutorial_name + ".meta.json")
        if os.path.exists(sidecar):
            try:
                with open(sidecar, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
                concept = meta.get("concept") or os.path.splitext(tutorial_name)[0]
                return concept, meta.get("via", "unknown")
            except (json.JSONDecodeError, OSError):
                pass
        return os.path.splitext(tutorial_name)[0], "unknown"


def _score_profile(root):
    """Per-concept levels from evidence.jsonl. Imported lazily and defensively:
    the dashboard must still render if scoring is missing or broken."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import score
        return score.profile(root)
    except Exception as exc:
        return {"concepts": {}, "headline": {"proven": 0, "recall": 0,
                                             "tracked": 0},
                "error": "%s: %s" % (type(exc).__name__, exc)}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value):
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


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _html_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


class Handler(BaseHTTPRequestHandler):
    state = None          # injected
    server_version = "grit/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[grit] " + (fmt % args) + "\n")

    def _send_html(self, code, html):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _dashboard(self):
        """The dashboard is a static file next to this daemon, not a Python
        f-string. It is the product's face and it changes often; templating it
        in here meant every colour tweak risked a server-side syntax error."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "dashboard.html")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ("<h1>grit</h1><p>dashboard.html is missing from "
                    + _html_escape(os.path.dirname(path)) + "</p>")

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Deliberately closed. The only clients are pages this daemon serves itself
    # (same origin, so they need no CORS header at all) and the assistant's CLI
    # (not a browser, so it is unaffected).
    #
    # This used to echo any `http://localhost:*` origin, which on a developer's
    # machine is not a boundary: every `npm run dev` in every cloned repo gets a
    # localhost origin. Any such page could read /ledger — every concept you
    # failed, every justification verbatim — which is precisely the liability
    # DESIGN §8 exists to prevent.
    def _cors(self):
        self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")

    def _json(self, code, obj):
        body = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send_html(200, self._dashboard())
        if path == "/health":
            return self._json(200, {"ok": True, "root": self.state.root})
        if path == "/preferences":
            return self._json(200, self.state.load_prefs())
        if path == "/score":
            return self._json(200, _score_profile(self.state.root))
        if path == "/status":
            # One request instead of several shell round-trips. What is wired
            # up, what has been recorded, and what is not built — the three
            # things an explicit `/grit` has to answer.
            auth = self.state.authorship()
            return self._json(200, {
                "score": _score_profile(self.state.root),
                "daemon": {"url": "http://%s:%d" % self.server.server_address[:2],
                           "root": self.state.root},
                "authorship": auth,
                "built": {"authorship_hook": True, "dashboard": True,
                          "tutorial_runtime": True},
                "not_built": ["tutorial generation"],
                "note": ("Repository tasks score today. Tutorials are a second "
                         "evidence source and their generator is not built."),
            })
        if path == "/authorship":
            return self._json(200, self.state.authorship())
        if path == "/themes":
            return self._json(200, {"themes": list(THEMES)})
        if path == "/tutorials":
            with self.state.lock:
                names = sorted(f for f in os.listdir(self.state.tutorials_dir)
                               if f.endswith(".html"))
                entries = list(self.state.ledger.get("entries", []))
            return self._json(200, {"tutorials": [
                {"name": n, **self.state.view_of_tutorial(n, entries)}
                for n in names]})
        if path == "/ledger":
            with self.state.lock:
                return self._json(200, self.state.ledger)
        if path == "/profile":
            # Kept as an alias so nothing that already points here breaks.
            # There is one profile now, and score.py owns it (ADR 0014).
            return self._json(200, _score_profile(self.state.root))
        if path.startswith("/tutorial/"):
            # Serve a tutorial by name, injecting a fresh session token.
            name = os.path.basename(self.path[len("/tutorial/"):].split("?")[0])
            path = os.path.join(self.state.tutorials_dir, name)
            if not os.path.exists(path) or not os.path.abspath(path).startswith(
                    os.path.abspath(self.state.tutorials_dir)):
                return self._json(404, {"error": "no such tutorial"})
            # Concept identity is NOT the filename (ADR 0010). Prefer a sidecar
            # `<name>.meta.json` with {"concept": "token-bucket", "via": "..."};
            # fall back to the stem so hand-copied tutorials still work.
            concept, via = self.state.concept_of(name)
            token, judge_token = self.state.open_session(
                concept, path, routing_via=via)
            with open(path, "r", encoding="utf-8") as fh:
                html = fh.read()
            base = "http://%s:%d" % (self.server.server_address[0],
                                     self.server.server_address[1])
            # The judge token goes to the operator's terminal, never to the
            # browser. This is the split that makes gate 3 the assistant's.
            sys.stderr.write(
                "[grit] session for '%s' — judge with:\n"
                "       curl -s -X POST %s/judgment/%s "
                "-H 'Content-Type: application/json' "
                "-d '{\"judgment\":\"sound\"}'\n"
                % (concept, base, judge_token))
            # Hand the page its REPORT token without touching the file on disk.
            html = html.replace(
                "</head>",
                "<script>window.GRIT_SESSION=" + json.dumps(token)
                + ";window.GRIT_DAEMON=" + json.dumps(base) + ";</script></head>",
                1)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, ValueError):
            return self._json(400, {"error": "bad json"})

        parts = [p for p in self.path.split("/") if p]

        # /preferences — the dashboard's only write. Onboarding lands here.
        if len(parts) == 1 and parts[0] == "preferences":
            return self._json(200, self.state.save_prefs(payload))

        # /judgment/<judge-token> — gate 3, on a SEPARATE path and a separate
        # credential. Never reachable with the token the page holds.
        if len(parts) == 2 and parts[0] == "judgment":
            entry, err = self.state.judge(
                parts[1], payload.get("judgment"), payload.get("message", ""))
            if err:
                return self._json(400, {"error": err})
            return self._json(200, {"ok": True, "earned": entry.get("earned"),
                                    "judgment": entry.get("judgment")})

        # /tutorial/<report-token>/<event> — the two gates the page may report.
        if len(parts) == 3 and parts[0] == "tutorial":
            token, event = parts[1], parts[2]
            if event in ("check", "justification"):
                entry, err = self.state.record(token, event, payload)
            elif event == "judgment":
                # The page asking to judge itself is the attack this split
                # exists to stop. Refuse loudly rather than 404.
                return self._json(403, {
                    "error": "judgment-requires-judge-token",
                    "detail": "gate 3 is the assistant's; the page cannot award it",
                })
            else:
                return self._json(404, {"error": "unknown event " + event})
            if err:
                return self._json(400, {"error": err})
            return self._json(200, {
                "ok": True,
                "judgment": entry.get("judgment", "pending"),
                "message": entry.get("judgment_message", ""),
                "earned": entry.get("earned", False),
                "gates_present": entry.get("gates_present", []),
                "gates_required": entry.get("gates_required", list(GATES)),
            })
        return self._json(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser(description="grit local daemon")
    ap.add_argument("--port", type=int, default=int(os.environ.get(
        "GRIT_PORT", DEFAULT_PORT)),
        help="0 picks any free port; the real one is written to daemon.json")
    ap.add_argument("--root", default=os.path.expanduser(
        os.environ.get("GRIT_ROOT", "~/.grit")))
    ap.add_argument("--host", default=os.environ.get("GRIT_HOST", "127.0.0.1"))
    ap.add_argument("--daemon", action="store_true",
                    help="detach and keep running after this shell exits")
    ap.add_argument("--stop", action="store_true",
                    help="stop the daemon named in <root>/daemon.json")
    args = ap.parse_args()

    where = os.path.join(os.path.expanduser(args.root), "daemon.json")

    if args.stop:
        try:
            with open(where, encoding="utf-8") as fh:
                pid = json.load(fh)["pid"]
            os.kill(pid, signal.SIGTERM)
            print("stopped pid %d" % pid)
        except (OSError, ValueError, KeyError):
            print("nothing to stop (no live daemon.json in %s)" % args.root)
        return 0

    if args.daemon:
        # Detach so the dashboard outlives the shell that started it. Closing a
        # terminal should not 404 your own data — that was the single biggest
        # day-to-day friction in this product.
        import subprocess
        argv = [sys.executable, os.path.abspath(__file__),
                "--root", args.root, "--host", args.host,
                "--port", str(args.port)]
        proc = subprocess.Popen(argv, start_new_session=True,
                                stdin=subprocess.DEVNULL,
                                stdout=open(os.path.join(
                                    os.path.expanduser(args.root),
                                    "daemon.log"), "ab"),
                                stderr=subprocess.STDOUT)
        for _ in range(50):                     # wait for it to publish itself
            time.sleep(0.1)
            try:
                with open(where, encoding="utf-8") as fh:
                    info = json.load(fh)
                if info.get("pid") == proc.pid:
                    print("grit serve — %s  (detached, pid %d)"
                          % (info["url"], proc.pid))
                    return 0
            except (OSError, ValueError):
                pass
        print("daemon did not start; see %s"
              % os.path.join(args.root, "daemon.log"), file=sys.stderr)
        return 1

    os.makedirs(args.root, exist_ok=True)
    Handler.state = State(args.root)
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        sys.stderr.write(
            "grit: cannot bind %s:%s — %s\n"
            "      Something else is using that port. Try:\n"
            "        python3 %s --port 0      (any free port)\n"
            "        GRIT_PORT=7802 python3 %s\n"
            % (args.host, args.port, exc.strerror or exc,
               sys.argv[0], sys.argv[0]))
        return 1

    # --port 0 means the kernel chose; ask the socket what we actually got.
    port = server.server_address[1]
    url = "http://%s:%d" % (args.host, port)

    # Publish where we are, so nothing downstream has to assume a port. The
    # assistant, the dashboard link and the judge command all read this instead
    # of hard-coding 7801 — which was wrong the moment anyone passed --port.
    with open(where, "w", encoding="utf-8") as fh:
        json.dump({"url": url, "host": args.host, "port": port,
                   "pid": os.getpid(), "root": args.root,
                   "started": _now()}, fh, indent=2)
    # NOTE: a SIGKILL (or a power cut) leaves this file behind pointing at a
    # dead port. Readers should treat it as a hint, not a promise — a failed
    # connection means "start the daemon", not "the daemon is broken".

    # `kill` sends SIGTERM, which Python does not turn into an exception — so
    # without this the address file outlives the process it describes.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print("grit serve — %s  (root: %s)" % (url, args.root))
    print("ledger: %s" % Handler.state.ledger_path)
    print("address published to: %s" % where)
    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        print("\nstopped")
    finally:
        # A stale address file sends the next reader to a dead port.
        try:
            with open(where, encoding="utf-8") as fh:
                if json.load(fh).get("pid") == os.getpid():
                    os.remove(where)
        except (OSError, ValueError):
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
