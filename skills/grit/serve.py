#!/usr/bin/env python3
"""
grit serve — the local daemon behind the dashboard.

Serves the dashboard and read-only views over the files the hook, verify_edit
and score.py write: the derived score, assistant authorship, task verdicts.
Its one write is preferences. Nothing here records evidence.

Binds to loopback only, and serves no cross-origin requests: every page that
talks to it is a page it served itself.

Run:  python3 serve.py [--port N|0] [--host H] [--root DIR]
      Env: GRIT_PORT, GRIT_HOST, GRIT_ROOT. The bound address is published
      to <root>/daemon.json so nothing downstream has to guess it.
"""

from __future__ import annotations

import argparse
import html
import importlib
import json
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import ModuleType
from typing import Any, Callable, Iterator, Optional

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
    "default_do_it_myself": True,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="grit local daemon")
    ap.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
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
        pid = _read_json(where, {})["pid"]
        os.kill(pid, signal.SIGTERM)
        print("stopped pid %d" % pid)
    except (OSError, KeyError, TypeError):
        print("nothing to stop (no live daemon.json in %s)" % root)
    return 0


def _spawn_daemon(args: argparse.Namespace, where: str) -> int:
    """Detach so the dashboard outlives the shell that started it."""
    import subprocess

    # The log opens before the child's own makedirs, and on a fresh machine
    # the root does not exist yet — the README's first command crashed here.
    os.makedirs(os.path.expanduser(args.root), exist_ok=True)
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
        info = _read_json(where, {})
        if isinstance(info, dict) and info.get("pid") == pid:
            return info
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
    """Write where we are, so nothing downstream has to assume a port — the
    assistant and the dashboard link both read this file.

    A SIGKILL leaves it behind pointing at a dead port, so readers treat it as
    a hint: a failed connection means "start the daemon", not "it is broken".
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
    info = _read_json(where, {})
    if isinstance(info, dict) and info.get("pid") == os.getpid():
        try:
            os.remove(where)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    state: State = None  # type: ignore[assignment]  # injected before serving

    server_version = "grit/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[grit] " + (fmt % args) + "\n")

    def _send_html(self, code: int, page: str) -> None:
        body = page.encode("utf-8")
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
                + html.escape(os.path.dirname(path))
                + "</p>"
            )

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Closed on purpose. Every client is a page this daemon served (same origin,
    # no header needed) or the assistant's CLI (not a browser). Allowing
    # `localhost:*` is not a boundary on a dev machine — any `npm run dev` in any
    # cloned repo gets one, and /authorship and /tasks carry every project you work in.
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
            "/tasks": self._serve_tasks,
            "/themes": self._serve_themes,
        }
        handler = routes.get(path)
        if handler is not None:
            return handler()
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

    def _serve_tasks(self) -> None:
        self._send_json(200, self.state.tasks())

    def _serve_themes(self) -> None:
        self._send_json(200, {"themes": list(THEMES)})

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
                "note": (
                    "Scores come only from repository tasks you did, "
                    "checked by verify_edit.py. An empty profile means no "
                    "task has been verified yet."
                ),
            },
        )

    def do_POST(self) -> None:
        """Route a write request."""
        payload = self._read_json_body()
        if payload is None:
            return self._send_json(400, {"error": "bad json"})

        # /preferences — the daemon's only write. Onboarding lands here.
        if self.path.split("?")[0] == "/preferences":
            return self._send_json(200, self.state.save_prefs(payload))
        return self._send_json(404, {"error": "not found"})

    def _read_json_body(self) -> Optional[dict[str, Any]]:
        """The request body as a dict, or None when it is not valid JSON."""
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, ValueError):
            return None

class State:
    """The daemon's view of <root>. Everything but preferences is read-only."""

    def __init__(self, root: str) -> None:
        self.root = root
        self.lock = threading.Lock()  # preferences are read-modify-write
        self.prefs_path = os.path.join(root, "preferences.json")

    def load_prefs(self) -> dict[str, Any]:
        return {**DEFAULT_PREFS, **_read_json(self.prefs_path, {})}

    def save_prefs(self, patch: Optional[dict[str, Any]]) -> dict[str, Any]:
        with self.lock:
            prefs = self.load_prefs()
            for key, value in (patch or {}).items():
                if key in DEFAULT_PREFS:  # ignore unknown keys, don't 400
                    prefs[key] = value
            if prefs.get("theme") not in THEMES:
                prefs["theme"] = DEFAULT_PREFS["theme"]
            _write_json_atomically(self.prefs_path, prefs)
            return prefs

    # ── Authorship ──────────────────────────────────────────────────────────
    def authorship(self) -> dict[str, Any]:
        """Aggregate every project's authorship log.

        Reports ONLY what was observed: lines the assistant wrote, and shell
        calls whose effect nobody watched. It deliberately does not compute a
        percentage — the human side is not observed at all, so any denominator
        here would be invented. `verify_edit.py` gets a real one per task, from
        git; this view does not pretend to.
        """
        out = [
            summary
            for summary in (
                self._read_project_log(path, project_dir)
                for path, project_dir in self._iter_project_dirs()
            )
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

    def _iter_project_dirs(self) -> Iterator[tuple[str, str]]:
        """(project path, its state directory) for every project the hook has
        seen. projects.json is the only index: the directories are hashed."""
        get_project_dir = _import_sibling("verify_edit").get_project_dir
        for path in _read_json(os.path.join(self.root, "projects.json"), []):
            yield path, get_project_dir(self.root, path)

    def tasks(self) -> dict[str, Any]:
        """Every handed-over task's latest verdict, newest first.

        This is the per-task answer to "how much did I do": the verdict comes
        from git plus the hook log, and the line counts from git, so unlike the
        authorship view it has a real denominator. A task verified twice shows
        its latest run; the file keeps every run.
        """
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for path, project_dir in self._iter_project_dirs():
            rows = _read_jsonl(os.path.join(project_dir, "tasks.jsonl"))
            for row in rows:
                latest[(path, str(row.get("task", "")))] = {**row, "project": path}
        tasks = sorted(latest.values(), key=lambda r: r.get("at", ""), reverse=True)
        totals: dict[str, int] = {}
        for row in tasks:
            verdict = str(row.get("verdict", "?"))
            totals[verdict] = totals.get(verdict, 0) + 1
        return {"tasks": tasks[:20], "totals": totals, "weeks": _count_by_week(tasks)}

    def _read_project_log(
        self, path: str, project_dir: str
    ) -> Optional[dict[str, Any]]:
        """One project's authorship summary, or None when it has no log."""
        log = os.path.join(project_dir, "authorship.jsonl")
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
        # Offered, and no file edit happened: neither an unprompted one, nor the
        # prompted one confirmed by PostToolUse. Without a PostToolUse
        # registration (older installs) an approved prompted edit with nothing
        # after it still reads as taken — the inference this used to be.
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
        if row.get("event") == "applied":
            edit_sessions.add(row.get("session", ""))
            return
        if row.get("author") != "assistant":
            return
        if row.get("opaque"):
            # Not a decline signal: in DIY mode the assistant still runs the
            # user's tests through the shell.
            summary.shell += 1
            return
        if not row.get("prompted"):
            edit_sessions.add(row.get("session", ""))
        summary.edits += 1
        summary.lines += int(row.get("lines") or 0)
        if row.get("file"):
            summary.files.add(row["file"])

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
                    "Your saved default is to hand work straight over. Work "
                    "done that way is not scored."
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
            "headline": {"shipped": 0, "practised": 0, "tracked": 0},
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


def _read_json(path: str, default: Any) -> Any:
    """The file's JSON, or `default` when it is missing or unreadable. Every
    file here is optional state, so a bad one degrades rather than raises."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _count_by_week(
    tasks: list[dict[str, Any]], weeks: int = 8, now: Optional[datetime] = None
) -> list[dict[str, Any]]:
    """Verdict counts for each of the last `weeks` ISO weeks, oldest first.
    Empty weeks are kept: a gap is part of the trend, not missing data."""
    now = now or datetime.now(timezone.utc)
    keys = [_week_key(now - timedelta(weeks=n)) for n in range(weeks - 1, -1, -1)]
    counts: dict[str, dict[str, int]] = {k: {} for k in keys}
    for row in tasks:
        at = _parse_iso(row.get("at"))
        bucket = counts.get(_week_key(at)) if at else None
        if bucket is not None:
            verdict = str(row.get("verdict", "?"))
            bucket[verdict] = bucket.get(verdict, 0) + 1
    return [{"week": k, "verdicts": counts[k]} for k in keys]


def _week_key(when: datetime) -> str:
    year, week, _ = when.isocalendar()
    return "%d-W%02d" % (year, week)


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    """Every parseable row. One bad line must not void a project's record."""
    rows: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


def _write_json_atomically(path: str, data: Any) -> None:
    """Write JSON atomically: temp file, then rename.

    A crash must not half-write a file the next read depends on.
    """
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


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


if __name__ == "__main__":
    sys.exit(main() or 0)
