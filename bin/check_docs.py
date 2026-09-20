#!/usr/bin/env python3
"""Check the documentation's factual claims against the code.

    python3 bin/check_docs.py        # exits non-zero on any drift

Docs drift silently: paths to files nothing writes, endpoints nothing routes,
test counts nobody updated. Each class below has a definite answer in the
source, so it gets an assertion instead of a proofread.

NOT checked: prose, reasoning, tone — only claims with a definite answer.

Superseded ADRs are exempt; a superseded record describing the file it used to
govern is history, not drift.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Iterator, Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "grit"

# Historical by declaration: a worked example of a flow that no longer exists.
HISTORICAL = {"USAGE.md"}

# Vendored by the sdlc-* skills: a path catalogue and fill-in templates that
# describe what those skills would generate, not what this repository has. Their
# unfilled `{{placeholders}}` and forward references are not claims about grit.
VENDORED = ("CONVENTIONS.md", ".sdlc/templates/")

# (kind, where, message) — `where` is a path or a label, always stringified.
Finding = tuple[str, str, str]
findings: list[Finding] = []


def add(kind: str, where: Any, msg: str) -> None:
    findings.append((kind, str(where), msg))


def live_docs() -> Iterator[tuple[pathlib.Path, str]]:
    """Every doc that is meant to describe the product as it is today."""
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        if ".git" in p.parts or p.name in HISTORICAL:
            continue
        if any(v in rel for v in VENDORED):
            continue
        text = p.read_text(encoding="utf-8")
        if re.search(r"\*\*Status\*\*:\s*\*?\*?Superseded", text):
            continue  # history, exempt by design
        yield p, text


# ── The checks. One function per class, each pure with respect to the others:
# they only append to `findings`. Keeping them separate is what made the
# difference between a 277-line main() and something a reader can name.
def check_paths(serve: str, score: str) -> None:
    """§1 Repo paths in backticks must exist; §1b markdown links must resolve."""
    path_re = re.compile(
        r"`((?:\.sdlc|skills|hooks|bin|docs|tests)/[\w./-]+"
        r"\.(?:py|html|sh|json|jsonl|md))`"
    )
    for p, text in live_docs():
        for ref in set(path_re.findall(text)):
            if not (ROOT / ref).exists():
                add("MISSING PATH", p.relative_to(ROOT), ref)

    # A backtick path and a link target are two different syntaxes, and the
    # first version of this checker only looked at backticks — so a broken
    # [text](path) sailed straight through the very test written to catch it.
    link_re = re.compile(r"\]\((?!https?:|#)([^)]+\.(?:md|html|sh|py|json))\)")
    for p, text in live_docs():
        for ref in set(link_re.findall(text)):
            if not (p.parent / ref).resolve().exists():
                add("BROKEN LINK", p.relative_to(ROOT), ref)


def check_runtime_files(serve: str, score: str) -> None:
    """§2 Runtime files must be ones the code actually writes."""
    written = set(re.findall(r'"([a-z_]+\.jsonl?)"', serve + score))
    written |= {"authorship.jsonl", "daemon.log", "off"}
    dirs = {"tutorials", "snapshots", "asked"}
    runtime_re = re.compile(r"`(?:~/\.grit/|<project>/\.grit/|\./\.grit/)([\w./-]+)`")
    for p, text in live_docs():
        for ref in set(runtime_re.findall(text)):
            base = ref.rstrip("/").split("/")[0]
            if base not in written and base not in dirs:
                add("PHANTOM RUNTIME FILE", p.relative_to(ROOT), ref)


def check_endpoints(serve: str) -> None:
    """§3 Documented endpoints must be routed.

    Two shapes count as routed, because serve.py has had both: the route table
    (`"/health": self._serve_health`) it uses now, and the if-chain
    (`path == "/health"`) it used before. A checker that only understood one
    would report every endpoint as unrouted the moment the other was adopted —
    which is exactly what happened when the table landed.
    """
    routed = set(re.findall(r'"(/[a-z]+)":', serve))  # route table
    routed |= set(re.findall(r'path == "(/[a-z]+)"', serve))  # if-chain
    routed |= {"/" + n for n in re.findall(r'parts\[0\] == "([a-z]+)"', serve)}
    routed |= {"/", "/tutorial"}
    not_endpoints = {"/grit", "/v1"}  # slash command, upstream API
    for p, text in live_docs():
        for ep in set(re.findall(r"`(/[a-z]+)`", text)):
            if ep not in routed and ep not in not_endpoints:
                add("UNROUTED ENDPOINT", p.relative_to(ROOT), ep)


def check_cli_flags(serve: str, install: str) -> None:
    """§4 Documented CLI flags must exist in the scripts."""
    for p, text in live_docs():
        for flag in set(re.findall(r"install\.sh\s+(--[a-z-]+)", text)):
            if flag not in install:
                add("UNKNOWN FLAG", p.relative_to(ROOT), "install.sh " + flag)
        for flag in set(re.findall(r"serve\.py[^\n`]*?\s(--[a-z-]+)", text)):
            if '"%s"' % flag not in serve:
                add("UNKNOWN FLAG", p.relative_to(ROOT), "serve.py " + flag)


def check_scoring_constants(score: str) -> None:
    """§5 Scoring constants quoted in prose must match the code."""
    for label, needle in [
        ("repo 0.5", 'SOURCE_WEIGHT: dict[str, float] = {"repo": 0.5'),
        ("sandbox 0.2", '"sandbox": 0.2'),
        ("recall 0.30", "RECALL_AT = 0.30"),
        ("proven 0.80", "PROVEN_AT = 0.80"),
        ("per-task cap 1.5", "PER_TASK_CAP = 1.5"),
        ("two unaided tasks", "PROVEN_NEEDS_UNAIDED_TASKS = 2"),
        ("decay 90 days", "STALE_DAYS = 90"),
    ]:
        if needle not in score:
            add(
                "CONSTANT DRIFT",
                "score.py",
                "%s is quoted in the docs but no longer in the code" % label,
            )


def check_verdicts(verify: str) -> None:
    """§6 Verdict names must be ones verify_edit actually emits."""
    for verdict in ("HUMAN-WRITTEN", "ASSISTED", "UNVERIFIED", "NOTHING CHANGED"):
        if verdict not in verify:
            add(
                "VERDICT DRIFT",
                "verify_edit.py",
                "%s is documented but never emitted" % verdict,
            )


def check_test_counts() -> dict[str, Optional[int]]:
    """§7 Claimed test counts must match what the suites print."""
    real: dict[str, Optional[int]] = {}
    for label, cmd in {
        "daemon": [sys.executable, "-B", str(SKILL / "test_serve.py")],
        "hook": [sys.executable, "-B", str(ROOT / "hooks" / "test_hook.py")],
        "scoring": [sys.executable, "-B", str(SKILL / "score.py"), "selftest"],
    }.items():
        out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        m = re.search(r"ok — (\d+) (?:scoring )?propert", out.stdout)
        real[label] = int(m.group(1)) if m else None
    if None in real.values():
        add("SUITE DID NOT RUN", "tests", str(real))
    else:
        for p, text in live_docs():
            for n in re.findall(
                r"(\d+)\s+(?:integrity|hook|scoring|daemon)\s+propert", text
            ):
                if int(n) not in real.values():
                    add(
                        "STALE TEST COUNT",
                        p.relative_to(ROOT),
                        "doc says %s, suites report %s" % (n, real),
                    )
    return real


def check_computed_values(score_module: Any) -> None:
    """§8b Numbers quoted in prose must equal what the model COMPUTES.

    Constant DRIFT (§5) only proves a constant is still in the file. It cannot
    see prose that quotes a number the model no longer produces — which is how
    "plateaus around 0.4" survived the weights being halved, and how SKILL.md
    came to promise `proven` after one unaided task when the code wants two.
    """
    computed = _compute_quotable_numbers(score_module)
    for p_, text in live_docs():
        rel = p_.relative_to(ROOT)
        _check_plateau_claims(text, rel, computed["plateau"])
        _check_unaided_task_claims(text, rel, computed["needs_unaided"])


def _compute_quotable_numbers(score_module: Any) -> dict[str, Any]:
    """The numbers the docs are allowed to quote, computed from the model.

    A tutorial ground forever gives the plateau — the per-task cap is the
    ceiling.
    """
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    grounded = [
        score_module.EvidenceRow(
            at="2026-01-01T00:00:00+00:00",
            concept="c",
            source="sandbox",
            assistance="none",
            task="t",
            failed=False,
            project="",
        )
    ] * 50
    return {
        "plateau": round(score_module.score_concept(grounded, now).score, 4),
        "needs_unaided": score_module.PROVEN_NEEDS_UNAIDED_TASKS,
    }


def _check_plateau_claims(text: str, rel: Any, plateau: float) -> None:
    for m in re.finditer(r"plateaus? (?:at|around|to) ([0-9.]+)", text):
        if abs(float(m.group(1)) - plateau) > 1e-9:
            add(
                "COMPUTED VALUE DRIFT",
                rel,
                "doc says the plateau is %s; the model computes %s"
                % (m.group(1), plateau),
            )


def _check_unaided_task_claims(text: str, rel: Any, needs_unaided: int) -> None:
    words = {"one": 1, "two": 2, "three": 3, "four": 4}
    pat = (
        r"(one|two|three|four|\d+)\s+(?:distinct\s+)?unaided\s+"
        r"repository\s+(?:task|event)"
    )
    for m in re.finditer(pat, text, re.I):
        raw = m.group(1).lower()
        if int(words.get(raw, raw)) != needs_unaided:
            add(
                "COMPUTED VALUE DRIFT",
                rel,
                "doc says `proven` needs %s unaided repository task(s); "
                "PROVEN_NEEDS_UNAIDED_TASKS is %d" % (raw, needs_unaided),
            )


def check_cross_doc_agreement() -> None:
    """§8c Docs that state the same fact must state it the same way.

    Nothing above compares one document against another, so README could say
    the installer runs "both" self-checks while ARCHITECTURE said "all three"
    and neither tripped a check — they were wrong about each other, not about
    a path or a constant.
    """
    shared: dict[str, tuple[str, Callable[[re.Match[str]], str]]] = {
        "install.sh self-check count": (
            r"(both|all three|all four|\d+) self-checks must (?:all )?pass",
            lambda m: m.group(1).lower(),
        ),
    }
    for label, (pattern, norm_fn) in shared.items():
        answers: dict[str, list[str]] = {}
        for p_, text in live_docs():
            for m in re.finditer(pattern, text, re.I):
                answers.setdefault(norm_fn(m), []).append(str(p_.relative_to(ROOT)))
        if len(answers) > 1:
            add(
                "DOCS DISAGREE",
                label,
                " vs ".join(
                    "%r (%s)" % (k, ", ".join(sorted(set(v))))
                    for k, v in sorted(answers.items())
                ),
            )


def check_adr_citations() -> None:
    """§8d Every "ADR NNNN" anywhere must name an ADR that exists.

    Renumbering the set broke two references in .py files that a docs-only
    sweep never looked at. Code cites ADRs too, and a citation to a number
    nobody has is worse than none — it sends a reader hunting for a file.
    """
    live_adrs = {f.name[:4] for f in (ROOT / ".sdlc" / "docs" / "adr").glob("0*.md")}
    sources = [p_ for p_ in ROOT.rglob("*.py") if ".git" not in p_.parts]
    sources += [ROOT / "bin" / "install.sh"]
    sources += [p_ for p_, _ in live_docs()]
    for p_ in sources:
        if not p_.exists():
            continue
        for n in sorted(
            set(re.findall(r"ADR (\d{4})", p_.read_text(encoding="utf-8")))
        ):
            if n not in live_adrs:
                add("NO SUCH ADR", p_.relative_to(ROOT), "cites ADR %s" % n)


def check_adr_index() -> None:
    """§9 ADR index statuses must match the ADR files."""
    index = ROOT / ".sdlc" / "docs" / "adr" / "README.md"
    if not index.exists():
        return
    norm: Callable[[str], str] = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
    rows = re.findall(
        r"\[(\d{4})\]\(([^)]+)\)\s*\|[^|]+\|\s*([^|]+)\|", index.read_text()
    )
    for _, fname, status in rows:
        f = index.parent / fname
        if not f.exists():
            add("MISSING ADR", index.name, fname)
            continue
        m = re.search(r"- \*\*Status\*\*: (.+)", f.read_text())
        if (
            m
            and norm(status)[:8] not in norm(m.group(1))
            and norm(m.group(1))[:8] not in norm(status)
        ):
            add(
                "ADR STATUS MISMATCH",
                fname,
                "index says %r, file says %r" % (status.strip(), m.group(1).strip()),
            )


def _run_checks() -> None:
    """Every class of claim, in reading order. Each appends to `findings`."""
    serve = (SKILL / "serve.py").read_text()
    score = (SKILL / "score.py").read_text()
    install = (ROOT / "bin" / "install.sh").read_text()
    verify = (SKILL / "verify_edit.py").read_text()

    check_paths(serve, score)
    check_runtime_files(serve, score)
    check_endpoints(serve)
    check_cli_flags(serve, install)
    check_scoring_constants(score)
    check_verdicts(verify)
    check_test_counts()

    sys.path.insert(0, str(SKILL))
    import score as S

    check_computed_values(S)
    check_cross_doc_agreement()
    check_adr_citations()
    check_adr_index()


def main() -> int:
    _run_checks()
    if not findings:
        print("docs ok — 12 classes of claim checked against the code")
        return 0
    _print_findings()
    return 1


def _print_findings() -> None:
    grouped: dict[str, list[tuple[str, str]]] = {}
    for kind, where, msg in findings:
        grouped.setdefault(kind, []).append((where, msg))
    for kind, items in sorted(grouped.items()):
        print("\n%s (%d)" % (kind, len(items)))
        for where, msg in items:
            print("   %-44s %s" % (where, msg))
    print("\n%d stale claim(s). Fix the doc, or fix the code." % len(findings))


if __name__ == "__main__":
    sys.exit(main())
