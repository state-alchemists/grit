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

import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "grit"

# Historical by declaration: a worked example of a flow that no longer exists.
HISTORICAL = {"USAGE.md"}

findings = []


def add(kind, where, msg):
    findings.append((kind, str(where), msg))


def live_docs():
    """Every doc that is meant to describe the product as it is today."""
    for p in sorted(ROOT.rglob("*.md")):
        if ".git" in p.parts or p.name in HISTORICAL:
            continue
        text = p.read_text(encoding="utf-8")
        if re.search(r"\*\*Status\*\*:\s*\*?\*?Superseded", text):
            continue  # history, exempt by design
        yield p, text


def main():
    serve = (SKILL / "serve.py").read_text()
    score = (SKILL / "score.py").read_text()
    install = (ROOT / "bin" / "install.sh").read_text()
    verify = (SKILL / "verify_edit.py").read_text()

    # ── 1. Repo paths in backticks must exist ────────────────────────────────
    path_re = re.compile(
        r"`((?:skills|hooks|bin|docs|tests)/[\w./-]+"
        r"\.(?:py|html|sh|json|jsonl|md))`"
    )
    for p, text in live_docs():
        for ref in set(path_re.findall(text)):
            if not (ROOT / ref).exists():
                add("MISSING PATH", p.relative_to(ROOT), ref)

    # ── 1b. Markdown links must resolve ──────────────────────────────────────
    # A backtick path and a link target are two different syntaxes, and the
    # first version of this checker only looked at backticks — so a broken
    # [text](path) sailed straight through the very test written to catch it.
    link_re = re.compile(r"\]\((?!https?:|#)([^)]+\.(?:md|html|sh|py|json))\)")
    for p, text in live_docs():
        for ref in set(link_re.findall(text)):
            if not (p.parent / ref).resolve().exists():
                add("BROKEN LINK", p.relative_to(ROOT), ref)

    # ── 2. Runtime files must be ones the code actually writes ───────────────
    written = set(re.findall(r'"([a-z_]+\.jsonl?)"', serve + score))
    written |= {"authorship.jsonl", "daemon.log", "off"}
    dirs = {"tutorials", "snapshots", "asked"}
    runtime_re = re.compile(r"`(?:~/\.grit/|<project>/\.grit/|\./\.grit/)([\w./-]+)`")
    for p, text in live_docs():
        for ref in set(runtime_re.findall(text)):
            base = ref.rstrip("/").split("/")[0]
            if base not in written and base not in dirs:
                add("PHANTOM RUNTIME FILE", p.relative_to(ROOT), ref)

    # ── 3. Documented endpoints must be routed ───────────────────────────────
    routed = set(re.findall(r'path == "(/[a-z]+)"', serve))
    routed |= {"/" + n for n in re.findall(r'parts\[0\] == "([a-z]+)"', serve)}
    routed |= {"/", "/tutorial"}
    not_endpoints = {"/grit", "/v1"}  # slash command, upstream API
    for p, text in live_docs():
        for ep in set(re.findall(r"`(/[a-z]+)`", text)):
            if ep not in routed and ep not in not_endpoints:
                add("UNROUTED ENDPOINT", p.relative_to(ROOT), ep)

    # ── 4. Documented CLI flags must exist ───────────────────────────────────
    for p, text in live_docs():
        for flag in set(re.findall(r"install\.sh\s+(--[a-z-]+)", text)):
            if flag not in install:
                add("UNKNOWN FLAG", p.relative_to(ROOT), "install.sh " + flag)
        for flag in set(re.findall(r"serve\.py[^\n`]*?\s(--[a-z-]+)", text)):
            if '"%s"' % flag not in serve:
                add("UNKNOWN FLAG", p.relative_to(ROOT), "serve.py " + flag)

    # ── 5. Scoring constants quoted in prose must match the code ─────────────
    for label, needle in [
        ("repo 0.5", 'SOURCE_WEIGHT = {"repo": 0.5'),
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

    # ── 6. Verdict names must be ones verify_edit actually emits ─────────────
    for verdict in ("HUMAN-WRITTEN", "ASSISTED", "UNVERIFIED", "NOTHING CHANGED"):
        if verdict not in verify:
            add(
                "VERDICT DRIFT",
                "verify_edit.py",
                "%s is documented but never emitted" % verdict,
            )

    # ── 7. Claimed test counts must match what the suites print ──────────────
    real = {}
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

    # ── 8b. Numbers quoted in prose must equal what the model COMPUTES ───────
    # Constant DRIFT (§5) only proves a constant is still in the file. It cannot
    # see prose that quotes a number the model no longer produces — which is how
    # "plateaus around 0.4" survived the weights being halved, and how SKILL.md
    # came to promise `proven` after one unaided task when the code wants two.
    sys.path.insert(0, str(SKILL))
    import score as S

    at = "2026-01-01T00:00:00+00:00"
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)

    def run(evs):
        return S.score_concept(evs, now)

    def sandbox(n):
        return [
            {
                "at": at,
                "source": "sandbox",
                "assistance": "none",
                "task": "t",
                "failed": False,
                "project": "",
            }
        ] * n

    computed = {
        # a tutorial ground forever — the per-task cap is the ceiling
        "plateau": round(run(sandbox(50))["score"], 4),
        "needs_unaided": S.PROVEN_NEEDS_UNAIDED_TASKS,
    }
    words = {"one": 1, "two": 2, "three": 3, "four": 4}

    for p_, text in live_docs():
        rel = p_.relative_to(ROOT)
        for m in re.finditer(r"plateaus? (?:at|around|to) ([0-9.]+)", text):
            if abs(float(m.group(1)) - computed["plateau"]) > 1e-9:
                add(
                    "COMPUTED VALUE DRIFT",
                    rel,
                    "doc says the plateau is %s; the model computes %s"
                    % (m.group(1), computed["plateau"]),
                )
        pat = (
            r"(one|two|three|four|\d+)\s+(?:distinct\s+)?unaided\s+"
            r"repository\s+(?:task|event)"
        )
        for m in re.finditer(pat, text, re.I):
            raw = m.group(1).lower()
            n = words.get(raw, raw)
            if int(n) != computed["needs_unaided"]:
                add(
                    "COMPUTED VALUE DRIFT",
                    rel,
                    "doc says `proven` needs %s unaided repository task(s); "
                    "PROVEN_NEEDS_UNAIDED_TASKS is %d"
                    % (raw, computed["needs_unaided"]),
                )

    # ── 8c. Docs that state the same fact must state it the same way ─────────
    # Nothing above compares one document against another, so README could say
    # the installer runs "both" self-checks while ARCHITECTURE said "all three"
    # and neither tripped a check — they were wrong about each other, not about
    # a path or a constant.
    shared = {
        "install.sh self-check count": (
            r"(both|all three|all four|\d+) self-checks must (?:all )?pass",
            lambda m: m.group(1).lower(),
        ),
    }
    for label, (pattern, norm_fn) in shared.items():
        answers = {}
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

    # ── 8c-bis. Claims known to be FALSE must not come back ──────────────────
    # "nothing generates a tutorial" was repeated across five docs, the /status
    # payload and the dashboard's empty state. It is not true: the assistant
    # authors one from tutorial.template.html, and the loop was driven end to
    # end on 2026-09-14 — three gates, evidence row, level. What is missing is
    # automation around that, which is a different and much smaller claim.
    #
    # A cross-doc agreement check made this WORSE: every doc agreed, so nothing
    # fired, and a file telling the truth would have been the one flagged.
    BANNED = [
        (r"nothing (?:generates|writes) a tutorial",
         "the assistant writes them; say 'not automated' instead"),
        (r"there is no (?:tutorial )?generator",
         "the assistant is the generator; say 'no library / no automation'"),
        (r"generator (?:is (?:still )?unbuilt|does not exist|is not built)",
         "verified working end to end; name the missing automation instead"),
        (r"no generator\b",
         "verified working end to end; name the missing automation instead"),
    ]
    code_and_docs = [p_ for p_, _ in live_docs()]
    code_and_docs += [ROOT / "skills" / "grit" / "serve.py",
                      ROOT / "skills" / "grit" / "dashboard.html",
                      ROOT / "skills" / "grit" / "SKILL.md"]
    for p_ in code_and_docs:
        if not p_.exists():
            continue
        body = p_.read_text(encoding="utf-8")
        for pattern, why in BANNED:
            if re.search(pattern, body, re.I):
                add("KNOWN-FALSE CLAIM", p_.relative_to(ROOT), why)

    # ── 8d. Every "ADR NNNN" anywhere must name an ADR that exists ───────────
    # Renumbering the set broke two references in .py files that a docs-only
    # sweep never looked at. Code cites ADRs too, and a citation to a number
    # nobody has is worse than none — it sends a reader hunting for a file.
    live_adrs = {f.name[:4] for f in (ROOT / "docs" / "adr").glob("0*.md")}
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

    # ── 9. ADR index statuses must match the ADR files ───────────────────────
    index = ROOT / "docs" / "adr" / "README.md"
    if index.exists():
        norm = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
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
                    "index says %r, file says %r"
                    % (status.strip(), m.group(1).strip()),
                )

    # ── report ───────────────────────────────────────────────────────────────
    if not findings:
        print("docs ok — 13 classes of claim checked against the code")
        return 0
    grouped = {}
    for kind, where, msg in findings:
        grouped.setdefault(kind, []).append((where, msg))
    for kind, items in sorted(grouped.items()):
        print("\n%s (%d)" % (kind, len(items)))
        for where, msg in items:
            print("   %-44s %s" % (where, msg))
    print("\n%d stale claim(s). Fix the doc, or fix the code." % len(findings))
    return 1


if __name__ == "__main__":
    sys.exit(main())
