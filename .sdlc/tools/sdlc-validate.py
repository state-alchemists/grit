#!/usr/bin/env python3
"""sdlc-validate.py — deterministic validator for SDLC artifacts.

Installed into a project at `.sdlc/tools/sdlc-validate.py` by `/sdlc-init`.
Run it by hand, from a skill ("validate -> fix -> repeat"), or as a CI gate.
Stdlib only; Python 3.8+.

This file is the only copy — skills install it, none of them embed it.

USAGE
    python3 sdlc-validate.py [--root DIR] [--feature SLUG] [--strict] [--json]

    --root DIR     Project root to scan (default: current directory).
    --feature SLUG Restrict checks to one feature directory (default: all).
    --strict       Make warnings exit non-zero too.
    --json         Emit a machine-readable JSON report instead of text.

EXIT CODES
    0  clean (no errors; warnings allowed unless --strict)
    1  warnings present and --strict
    2  errors present

ID & TRACEABILITY SCHEME (see .sdlc/CONVENTIONS.md)
    - Each spec.md declares `**Feature Key:** KEY` (uppercase, globally unique).
    - Requirement IDs are per-feature (REQ-001, NFR-001, UT-001, ...) and made
      globally unambiguous by the key.
    - The test plan lives in spec.md under `## Test Plan`. A separate
      `.sdlc/tests/<slug>/test-plan.md` is read as a legacy fallback.
    - Source headers:  IMPLEMENTS: KEY:REQ-001, KEY:NFR-002
    - Test headers:    COVERS: KEY:REQ-002, KEY:UT-005, KEY:IT-001
    - Inline tags:     @sdlc KEY:REQ-003, KEY:REQ-004
    - Legacy (unkeyed) tags such as `@sdlc REQ-003` are tolerated with a WARNING.

CHECKS
    1  Feature key uniqueness ........................... ERROR
    2  Traceability: code coverage (IMPLEMENTS) ......... ERROR
    3  Traceability: test coverage (COVERS) ............. ERROR
    4  Dangling tag (references a non-existent ID) ...... ERROR
    5  Unkeyed tag ...................................... WARNING
    6  Duplicate active ID within a feature ............. ERROR
    7  Recycled removed ID .............................. ERROR
    8  EARS syntax (deprecated dialect / no SHALL) ...... WARNING
    9  Test-plan coverage of spec ....................... WARNING
   10  Legacy layout detected ........................... INFO
   11  Missing test plan ................................ WARNING
"""

import argparse
import json
import os
import re
import sys

ERROR, WARNING, INFO = "ERROR", "WARNING", "INFO"

EXIT_CLEAN, EXIT_WARNINGS, EXIT_ERRORS = 0, 1, 2

# Directories and extensions never scanned for traceability tags.
SKIPPED_DIRECTORIES = {
    ".git", ".sdlc", "node_modules", "dist", "build", "__pycache__",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", "target", ".next",
    "coverage", ".tox",
}
SKIPPED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".tar", ".lock",
    ".ico", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".bin", ".so",
    ".dll", ".dylib", ".class", ".jar", ".wasm", ".pyc",
}
MAX_SCANNED_BYTES = 2 * 1024 * 1024

FEATURE_KEY_PATTERN = re.compile(r"^\*\*Feature Key:\*\*\s*([A-Z][A-Z0-9_-]*)", re.M)
# An ID token, optionally key-prefixed: KEY:REQ-001 or REQ-001.
TAG_TOKEN_PATTERN = re.compile(
    r"\b(?:([A-Z][A-Z0-9_-]*):)?((?:REQ|NFR|UT|IT|E2E|PBT)-\d+)\b")
# A requirement or NFR definition line in spec.md.
REQUIREMENT_LINE_PATTERN = re.compile(r"^\s*[-*|]?\s*`?((?:REQ|NFR)-\d+)`?\b(.*)$")
TEST_ID_PATTERN = re.compile(r"\b((?:UT|IT|E2E|PBT)-\d+)\b")
NFR_ID_PATTERN = re.compile(r"`?(NFR-\d+)`?$")
IMPLEMENTS_PATTERN = re.compile(r"IMPLEMENTS:\s*(.+)")
COVERS_PATTERN = re.compile(r"COVERS:\s*(.+)")
INLINE_TAG_PATTERN = re.compile(r"@sdlc\s+(.+)")
TEST_PLAN_HEADING_PATTERN = re.compile(r"^#{2,3}\s+Test Plan\b", re.M)

# EARS keywords are uppercase by convention (see CONVENTIONS.md), so these match
# case-SENSITIVELY. Otherwise the ordinary English words "as" and "unless"
# inside a canonical requirement ("IF a file is uploaded as a draft, THEN ...")
# read as the deprecated dialect. Leading-keyword patterns are anchored to the
# start of the requirement for the same reason.
DEPRECATED_EARS_PATTERNS = [
    (re.compile(r"\bALWAYS\s+SHALL\b"),
     "ALWAYS SHALL -> ubiquitous (drop ALWAYS): 'The <system> SHALL ...'"),
    (re.compile(r"^\s*WHERE\b.+\bTHEN\b"),
     "WHERE ... THEN (state-driven) -> 'WHILE ..., the <system> SHALL ...'"),
    (re.compile(r"^\s*AS\b.+\bTHEN\b"),
     "AS ... THEN -> 'IF ..., THEN ... SHALL ...'"),
    (re.compile(r"\bUNLESS\b"),
     "UNLESS -> 'IF NOT ..., THEN ... SHALL ...' (or WHERE)"),
]

# Mechanisms that validate an NFR outside application code, matched against the
# "Validated By" cell of an NFR table row. CI/CD is deliberately absent: CI is
# where validation runs, not what performs it, so "load test in CI" is validated
# by code and still needs IMPLEMENTS/COVERS. An NFR genuinely validated by a CI
# gate is declared under the "NFRs Validated Outside Code" heading instead.
# ponytail: word list, not a classifier -- widen it if real specs need it.
OUTSIDE_CODE_PATTERN = re.compile(
    r"\b(infra|manual|process|sla|slo|terraform|waf|dashboard)\b", re.I)

# A requirement is retired only when its text BEGINS with REMOVED (the
# documented form is `REQ-NNN: REMOVED ({date}) -- {reason}`). A substring test
# would retire any requirement that merely mentions a removed thing.
REMOVED_MARKER_PATTERN = re.compile(r"^[\s`:*_|()\-—]*REMOVED\b")

# Legacy artifact locations, reported so the user knows to run /sdlc-adopt.
LEGACY_LAYOUT_PAIRS = [
    (os.path.join("docs"), os.path.join(".sdlc", "docs"), "steering docs"),
    (os.path.join("requirements"), os.path.join(".sdlc", "requirements"), "requirements"),
    (os.path.join("specs"), os.path.join(".sdlc", "specs"), "specs"),
    (os.path.join("reviews"), os.path.join(".sdlc", "reviews"), "reviews"),
    ("rules.md", os.path.join(".sdlc", "rules.md"), "rules"),
]


def main(argv=None):
    """Parse arguments, validate the project, emit the report, return an exit code."""
    parser = argparse.ArgumentParser(
        description="Validate SDLC traceability, EARS, and ID hygiene.")
    parser.add_argument("--root", default=".", help="project root (default: .)")
    parser.add_argument("--feature", default=None, help="restrict to one feature slug")
    parser.add_argument("--strict", action="store_true",
                        help="warnings exit non-zero too")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    arguments = parser.parse_args(argv)

    root = os.path.abspath(arguments.root)
    report = validate_project(root, only_feature=arguments.feature)

    if arguments.json:
        emit_json_report(report)
    else:
        emit_text_report(report)

    error_count, warning_count, _ = report.count_by_severity()
    if error_count:
        return EXIT_ERRORS
    if warning_count and arguments.strict:
        return EXIT_WARNINGS
    return EXIT_CLEAN


def validate_project(root, only_feature=None, report=None):
    """Run every check over the project at `root` and return the filled Report."""
    report = report or Report()

    check_legacy_layout(root, report)

    spec_paths_by_slug = get_spec_paths_by_slug(root)
    if only_feature:
        spec_paths_by_slug = {
            slug: path for slug, path in spec_paths_by_slug.items()
            if slug == only_feature
        }
    if not spec_paths_by_slug:
        report.info("no-specs",
                    "No SDLC specs found (looked in .sdlc/specs/ and specs/).")
        return report

    specs_by_slug, slug_by_key = check_spec_hygiene(root, spec_paths_by_slug, report)
    tags = collect_traceability_tags(root)
    valid_targets = get_valid_tag_targets(specs_by_slug)
    check_tag_targets(tags, valid_targets, slug_by_key, report)
    check_requirement_coverage(root, specs_by_slug, spec_paths_by_slug, tags, report)
    return report


def check_legacy_layout(root, report):
    """Check 10 — report SDLC artifacts still sitting at pre-`.sdlc/` paths."""
    for legacy_path, canonical_path, label in LEGACY_LAYOUT_PAIRS:
        legacy_full = os.path.join(root, legacy_path)
        canonical_full = os.path.join(root, canonical_path)
        if os.path.exists(legacy_full) and not os.path.exists(canonical_full):
            report.info(
                "legacy-layout",
                "Legacy %s at %s — run /sdlc-adopt to consolidate under .sdlc/."
                % (label, legacy_path),
                legacy_path)


def check_spec_hygiene(root, spec_paths_by_slug, report):
    """Checks 1, 6, 7, 8 — parse every spec and validate keys, IDs, and EARS.

    Returns (specs_by_slug, slug_by_key).
    """
    specs_by_slug = {}
    slug_by_key = {}
    for slug, spec_path in spec_paths_by_slug.items():
        text = read_file_text(spec_path)
        location = os.path.relpath(spec_path, root)
        if text is None:
            report.error("read", "Could not read spec", location)
            continue

        spec = parse_spec(text)
        if not spec["feature_key"]:
            spec["feature_key"] = slug.upper()
            report.info("feature-key",
                        "No '**Feature Key:**' declared; defaulting to '%s'. "
                        "Declare one explicitly." % spec["feature_key"], location)
        feature_key = spec["feature_key"]

        # Check 1: feature key uniqueness.
        if feature_key in slug_by_key and slug_by_key[feature_key] != slug:
            report.error("key-unique",
                         "Feature Key '%s' is also used by feature '%s'."
                         % (feature_key, slug_by_key[feature_key]), location)
        else:
            slug_by_key[feature_key] = slug

        # Check 6: an ID defined active more than once.
        for requirement_id in sorted(set(spec["duplicate_ids"])):
            report.error("dup-id",
                         "ID %s defined more than once (active) in %s."
                         % (requirement_id, slug), location)

        # Check 7: an ID marked REMOVED that is also still active.
        recycled_ids = spec["removed_ids"] & set(spec["active_ids"])
        for requirement_id in sorted(recycled_ids):
            report.error("recycled-id",
                         "ID %s is marked REMOVED but also appears active."
                         % requirement_id, location)

        # Check 8: EARS dialect.
        check_ears_syntax(spec["requirement_texts"], location, report)

        # Check 11 — must happen here, not during the coverage pass: a legacy
        # test plan's UT-/IT- ids are legitimate COVERS targets, so they have to
        # be known before tags are resolved.
        resolve_test_plan(root, slug, spec, location, report)

        specs_by_slug[slug] = spec
    return specs_by_slug, slug_by_key


def resolve_test_plan(root, slug, spec, spec_location, report):
    """Check 11 — locate the feature's test plan and record it on the spec.

    The plan belongs in the spec's own `## Test Plan` section. A project
    migrated from the two-file layout keeps it at `.sdlc/tests/<slug>/test-plan.md`;
    that is read as a fallback so its test IDs stay valid COVERS targets.
    """
    spec["test_plan_location"] = spec_location
    if spec["test_plan_text"]:
        return

    legacy_path = find_first_existing_path(
        os.path.join(root, ".sdlc", "tests", slug, "test-plan.md"),
        os.path.join(root, "tests", slug, "test-plan.md"),
    )
    if not legacy_path:
        report.warn("missing-test-plan",
                    "Feature '%s' has no '## Test Plan' section in spec.md." % slug,
                    spec_location)
        return

    location = os.path.relpath(legacy_path, root)
    report.info("legacy-test-plan",
                "Feature '%s' keeps its test plan at %s — /sdlc-adopt folds it "
                "into spec.md." % (slug, location), location)
    spec["test_plan_text"] = read_file_text(legacy_path) or ""
    spec["test_plan_location"] = location
    spec["test_ids"] = set(TEST_ID_PATTERN.findall(spec["test_plan_text"]))


def check_ears_syntax(requirement_texts, location, report):
    """Check 8 — every requirement uses canonical EARS with an uppercase SHALL."""
    for requirement_id, text in sorted(requirement_texts.items()):
        deprecated_hint = get_deprecated_ears_hint(text)
        if deprecated_hint:
            report.warn("ears", "%s uses deprecated EARS dialect (%s)."
                        % (requirement_id, deprecated_hint), location)
            continue
        if not re.search(r"\bSHALL\b", text, re.I):
            report.warn("ears",
                        "%s has no SHALL/EARS keyword — restate in canonical EARS."
                        % requirement_id, location)


def get_deprecated_ears_hint(text):
    """Return the migration hint for the first deprecated pattern, else None."""
    for pattern, hint in DEPRECATED_EARS_PATTERNS:
        if pattern.search(text):
            return hint
    return None


def collect_traceability_tags(root):
    """Walk source and test files, returning every traceability tag found.

    Each tag is (feature_key_or_None, requirement_id, kind, relative_path).
    """
    tags = []
    for directory_path, directory_names, file_names in os.walk(root):
        directory_names[:] = [
            name for name in directory_names if name not in SKIPPED_DIRECTORIES
        ]
        for file_name in file_names:
            if os.path.splitext(file_name)[1].lower() in SKIPPED_EXTENSIONS:
                continue
            file_path = os.path.join(directory_path, file_name)
            text = read_file_text(file_path)
            if text is None:
                continue
            relative_path = os.path.relpath(file_path, root)
            for kind, parsed_tags in parse_traceability_tags(text).items():
                for feature_key, requirement_id in parsed_tags:
                    tags.append((feature_key, requirement_id, kind, relative_path))
    return tags


def get_valid_tag_targets(specs_by_slug):
    """Return the set of (feature_key, id) pairs a tag is allowed to reference."""
    valid_targets = set()
    for spec in specs_by_slug.values():
        feature_key = spec["feature_key"]
        for requirement_id in spec["active_ids"]:
            valid_targets.add((feature_key, requirement_id))
        for test_id in spec["test_ids"]:
            valid_targets.add((feature_key, test_id))
    return valid_targets


def check_tag_targets(tags, valid_targets, slug_by_key, report):
    """Checks 4 and 5 — every tag is key-namespaced and resolves to a real ID."""
    for feature_key, requirement_id, kind, relative_path in tags:
        if feature_key is None:
            report.warn("unkeyed-tag",
                        "Unkeyed tag '%s' in %s — re-key as KEY:%s."
                        % (requirement_id, kind, requirement_id), relative_path)
            continue
        if (feature_key, requirement_id) in valid_targets:
            continue
        if feature_key not in slug_by_key:
            report.error("dangling-tag",
                         "Tag %s:%s (%s) references unknown Feature Key '%s'."
                         % (feature_key, requirement_id, kind, feature_key),
                         relative_path)
        else:
            report.error("dangling-tag",
                         "Tag %s:%s (%s) references an ID not defined in feature '%s'."
                         % (feature_key, requirement_id, kind,
                            slug_by_key[feature_key]), relative_path)


def check_requirement_coverage(root, specs_by_slug, spec_paths_by_slug, tags, report):
    """Checks 2, 3, 9 — every requirement is implemented, tested, and planned."""
    implemented_targets = {
        (key, requirement_id)
        for key, requirement_id, kind, _ in tags
        if kind == "IMPLEMENTS" and key
    }
    covered_targets = {
        (key, requirement_id)
        for key, requirement_id, kind, _ in tags
        if kind == "COVERS" and key
    }

    for slug, spec in specs_by_slug.items():
        feature_key = spec["feature_key"]
        location = os.path.relpath(spec_paths_by_slug[slug], root)
        test_plan_text = spec["test_plan_text"]
        test_plan_location = spec["test_plan_location"]

        for requirement_id in sorted(spec["active_ids"]):
            if requirement_id in spec["outside_code_nfrs"]:
                report.info("outside-code",
                            "%s:%s validated outside code — exempt from "
                            "IMPLEMENTS/COVERS." % (feature_key, requirement_id),
                            location)
                continue
            if (feature_key, requirement_id) not in implemented_targets:
                report.error("trace-code",
                             "%s:%s has no IMPLEMENTS: header in any source file."
                             % (feature_key, requirement_id), location)
            if (feature_key, requirement_id) not in covered_targets:
                report.error("trace-test",
                             "%s:%s has no COVERS: header in any test file."
                             % (feature_key, requirement_id), location)
            is_planned = requirement_id in test_plan_text
            if requirement_id.startswith("REQ-") and test_plan_text and not is_planned:
                report.warn("plan-coverage",
                            "%s not referenced by any row in the test plan."
                            % requirement_id, test_plan_location)


def parse_spec(text):
    """Parse a spec.md into its feature key, requirement IDs, texts, and test plan."""
    feature_key_match = FEATURE_KEY_PATTERN.search(text)
    active_ids = {}          # id -> line number of its first active definition
    duplicate_ids = []
    removed_ids = set()
    requirement_texts = {}   # REQ id -> requirement text (active only)
    outside_code_nfrs = set()

    is_outside_code_section = False
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped_line = line.strip()
        if stripped_line.startswith("#"):
            is_outside_code_section = (
                "validated outside code" in stripped_line.lower())

        # An NFR table row exempts itself when its last cell (Validated By) names
        # an out-of-code mechanism. Checked before the definition match because a
        # table row also matches REQUIREMENT_LINE_PATTERN.
        outside_code_id = get_outside_code_nfr_id(line)
        if outside_code_id:
            outside_code_nfrs.add(outside_code_id)

        definition_match = REQUIREMENT_LINE_PATTERN.match(line)
        if not definition_match:
            continue
        requirement_id, remainder = definition_match.group(1), definition_match.group(2)

        if REMOVED_MARKER_PATTERN.match(remainder):
            removed_ids.add(requirement_id)
            continue

        is_repeated_nfr = is_outside_code_section and requirement_id.startswith("NFR-")
        if is_repeated_nfr:
            outside_code_nfrs.add(requirement_id)
        if requirement_id in active_ids:
            # Re-listing an NFR under "NFRs Validated Outside Code" is expected —
            # it is the same NFR as in the table, not a second definition.
            if not is_repeated_nfr:
                duplicate_ids.append(requirement_id)
        else:
            active_ids[requirement_id] = line_number

        if requirement_id.startswith("REQ-"):
            requirement_texts[requirement_id] = get_requirement_text(remainder)

    test_plan_text = get_test_plan_section(text)
    return {
        "feature_key": feature_key_match.group(1) if feature_key_match else None,
        "active_ids": active_ids,
        "duplicate_ids": duplicate_ids,
        "removed_ids": removed_ids,
        "requirement_texts": requirement_texts,
        "outside_code_nfrs": outside_code_nfrs,
        "test_plan_text": test_plan_text,
        "test_ids": set(TEST_ID_PATTERN.findall(test_plan_text)),
    }


def get_outside_code_nfr_id(line):
    """Return the NFR id of a table row validated outside code, else None."""
    if "|" not in line:
        return None
    cells = [cell.strip() for cell in line.split("|") if cell.strip()]
    if len(cells) < 2:
        return None
    id_match = NFR_ID_PATTERN.match(cells[0])
    if id_match and OUTSIDE_CODE_PATTERN.search(cells[-1]):
        return id_match.group(1)
    return None


def get_requirement_text(remainder):
    """Return the requirement prose that follows the ID and its optional citation."""
    if ":" in remainder:
        return remainder.split(":", 1)[1].strip()
    return remainder.strip()


def get_test_plan_section(text):
    """Return the text under the spec's `## Test Plan` heading, or '' if absent."""
    heading_match = TEST_PLAN_HEADING_PATTERN.search(text)
    if not heading_match:
        return ""
    section_start = heading_match.end()
    heading_level = len(heading_match.group(0).split()[0])
    next_heading = re.compile(r"^#{1,%d}\s+" % heading_level, re.M)
    next_match = next_heading.search(text, section_start)
    return text[section_start:next_match.start()] if next_match else text[section_start:]


def parse_traceability_tags(text):
    """Return {kind: [(feature_key_or_None, id), ...]} for one file's tags."""
    tags_by_kind = {"IMPLEMENTS": [], "COVERS": [], "@sdlc": []}
    patterns_by_kind = {
        "IMPLEMENTS": IMPLEMENTS_PATTERN,
        "COVERS": COVERS_PATTERN,
        "@sdlc": INLINE_TAG_PATTERN,
    }
    for line in text.splitlines():
        for kind, pattern in patterns_by_kind.items():
            match = pattern.search(line)
            if not match:
                continue
            for token in TAG_TOKEN_PATTERN.finditer(match.group(1)):
                tags_by_kind[kind].append((token.group(1), token.group(2)))
    return tags_by_kind


def get_spec_paths_by_slug(root):
    """Return {slug: spec_path} across the canonical and legacy spec locations."""
    spec_paths_by_slug = {}
    for base in (os.path.join(root, ".sdlc", "specs"), os.path.join(root, "specs")):
        if not os.path.isdir(base):
            continue
        for slug in sorted(os.listdir(base)):
            spec_path = os.path.join(base, slug, "spec.md")
            if os.path.exists(spec_path) and slug not in spec_paths_by_slug:
                spec_paths_by_slug[slug] = spec_path
    return spec_paths_by_slug


def find_first_existing_path(*paths):
    """Return the first path that exists, else None."""
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


def read_file_text(path):
    """Return a file's text, or None if it is missing, binary, or oversized."""
    try:
        if os.path.getsize(path) > MAX_SCANNED_BYTES:
            return None
        with open(path, "rb") as file_handle:
            raw_bytes = file_handle.read()
        if b"\x00" in raw_bytes:
            return None
        return raw_bytes.decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return None


class Report:
    """Collects findings, each one a (severity, check, message, location) tuple."""

    def __init__(self):
        self.findings = []

    def error(self, check, message, location=""):
        self.findings.append((ERROR, check, message, location))

    def warn(self, check, message, location=""):
        self.findings.append((WARNING, check, message, location))

    def info(self, check, message, location=""):
        self.findings.append((INFO, check, message, location))

    def count_by_severity(self):
        """Return (error_count, warning_count, info_count)."""
        severities = [finding[0] for finding in self.findings]
        return (severities.count(ERROR), severities.count(WARNING),
                severities.count(INFO))


def emit_text_report(report):
    """Print findings most-severe first, then the summary line."""
    severity_order = {ERROR: 0, WARNING: 1, INFO: 2}
    sorted_findings = sorted(report.findings,
                             key=lambda finding: severity_order[finding[0]])
    for severity, check, message, location in sorted_findings:
        suffix = " (%s)" % location if location else ""
        print("%s: %s — %s%s" % (severity, check, message, suffix))
    error_count, warning_count, info_count = report.count_by_severity()
    print("\n%d errors, %d warnings, %d info"
          % (error_count, warning_count, info_count))


def emit_json_report(report):
    """Print the same findings as JSON, for CI and other tools."""
    error_count, warning_count, info_count = report.count_by_severity()
    print(json.dumps({
        "summary": {
            "errors": error_count,
            "warnings": warning_count,
            "info": info_count,
        },
        "findings": [
            {"severity": severity, "check": check,
             "message": message, "location": location}
            for severity, check, message, location in report.findings
        ],
    }, indent=2))


if __name__ == "__main__":
    sys.exit(main())
