# Project Rules — Constitution

> Immutable invariants. Every SDLC skill reads this file and refuses to violate it.
> Override process: see RULE-999 below. Do not edit rule statements without an Override Record.

## How to Use This File
- Every spec, design, test plan, and implementation must respect every rule below.
- `/sdlc-review` reports a `FAIL` for any code that violates a rule.
- To change a rule, follow the Override Process (RULE-999) and append (do not edit) an entry to the Override Log.

## Rules

### RULE-001 — {{Short Title}}
| Field | Value |
|-------|-------|
| Category | {{Forbidden Patterns / Required Patterns / Compliance & Security / Quality Gates / Coding Standards}} |
| Statement | {{The rule, phrased as ALWAYS/NEVER}} |
| Rationale | {{Why this exists — past incident, regulation, team standard}} |
| Enforcement | {{How violations are detected — lint rule, review checklist, CI gate}} |
| Added | {{YYYY-MM-DD}} |

## Override Process — RULE-999
| Field | Value |
|-------|-------|
| Category | Process |
| Statement | {{Who approves an override and where it is recorded. Default: "A rule may only be overridden for a single change, recorded as an entry in the Override Log below, with the approver named. The rule statement itself is never edited."}} |
| Rationale | Prevents silent erosion of invariants. |
| Enforcement | Reviewers reject PRs that violate a rule without a matching Override Log entry. |

## Override Log

| Date | Rule | Scope (PR / commit) | Approver | Reason |
|------|------|---------------------|----------|--------|
| {{date}} | RULE-NNN | {{scope}} | {{approver}} | {{reason}} |
