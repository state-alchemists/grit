# Drift Report: {{FEATURE_NAME}} ({{KEY}})

*Dates: see `.sdlc/CONVENTIONS.md` § Dates and timestamps — run `date`, do not guess.*

**Documented at**: {{TIMESTAMP}}
**Scope**: {{scope}}
**Baseline**: {{existing spec.md / old-format requirements.md + design.md / none}}
**Source commit**: {{short sha}}

## Requirement Diff
| Old ID | New ID | Status | Note |
|--------|--------|--------|------|
| REQ-{{N}} | REQ-{{N}} | UNCHANGED / MODIFIED / ADDED / REMOVED-from-code | {{what changed}} |

## Needs a Decision
*`REMOVED-from-code`: the spec claims it, the code no longer does it — re-implement, or drop from the spec.*
*`ADDED`: the code does it, the spec never claimed it — formalize, or remove the undocumented behaviour.*

- {{REQ-NNN}}: {{decision needed}}

## Design Properties Found in Code
| Property | Finding |
|----------|---------|
| {{Property}} | {{enforced how, or "Not enforced — recommend adding {check}"}} |
