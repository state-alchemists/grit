# Quickfix: {{ONE-LINE DESCRIPTION}}

*Dates: see `.sdlc/CONVENTIONS.md` § Dates and timestamps — run `date`, do not guess.*

**Date**: {{TODAY}}
**Feature**: {{slug}}  **Key**: {{KEY}}
**Trigger**: {{Bug ticket / user request / observation}}
**Promoted**: {{yes — folded into spec.md / no — kept standalone}}

*Once `Promoted: yes`, this file is a historical record: its IDs live in `spec.md`, so the next-ID scan no longer needs it and it can move to `archive/`. A `Promoted: no` delta must stay beside `spec.md` — it is the only place its IDs are written down.*

## Behaviour Change Summary
{{One short paragraph: what the system did before, what it will do after, why.}}

## Requirements Delta
*Canonical EARS, uppercase keywords (WHEN / WHILE / WHERE / IF...THEN / ubiquitous SHALL).*

### ADDED
- `REQ-{{next-N}}`: {{EARS statement}}

### MODIFIED
- `REQ-{{existing-N}}` — was: "{{old text}}"
- `REQ-{{existing-N}}` — now: "{{new text}}"

### REMOVED
- `REQ-{{existing-N}}` — reason: {{why}}

## Design Impact
*List only properties this change affects; mark the rest "unchanged". Unlike the spec's Correctness section, a delta may say "unchanged" so the before/after is auditable.*

| Property | Before | After |
|----------|--------|-------|
| {{Property touched}} | {{state}} | {{state}} |

## Test Delta
*Rows here are promoted into the spec's `## Test Plan` section.*

### ADDED
- `UT-{{next-N}}`: test_{{function}}_{{condition}} — covers {{KEY}}:REQ-{{N}}

### MODIFIED
- `UT-{{existing-N}}` — updated expectation: {{describe}}

### REMOVED
- `UT-{{existing-N}}` — reason: {{why}}

## Rules Compliance
- {{Each RULE-* plausibly touched, with one line on why the change still complies. If none, "No applicable rules."}}

## Non-Regression Hints
{{Which existing tests must keep passing; which adjacent behaviours to verify manually.}}
