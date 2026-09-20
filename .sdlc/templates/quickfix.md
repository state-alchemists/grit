# Quickfix: {{ONE-LINE DESCRIPTION}}

**Date**: {{YYYY-MM-DD}}
**Feature**: {{slug}}  **Key**: {{KEY}}
**Trigger**: {{Bug ticket / user request / observation}}

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
