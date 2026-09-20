# SDLC Conventions

Single source of truth for paths, the EARS dialect, the ID/traceability scheme, and approval tiers. Every `sdlc-*` skill reads this file.

## Artifact paths (canonical)
| Artifact | Path |
|----------|------|
| Steering docs | `.sdlc/docs/` |
| ADRs | `.sdlc/docs/adr/` |
| Architecture | `.sdlc/docs/architecture.md` |
| Requirements | `.sdlc/requirements/` |
| Specs (requirements + design + test plan) | `.sdlc/specs/<slug>/spec.md` |
| Reviews | `.sdlc/reviews/<slug>/report-{YYYY-MM-DDTHH-MM-SS}.md` |
| Rules | `.sdlc/rules.md` |
| Templates | `.sdlc/templates/` |
| Validator | `.sdlc/tools/sdlc-validate.py` |

**Legacy fallback**: older projects keep steering docs at `docs/`, ADRs at `docs/adr/`, requirements at `requirements/`, rules at `rules.md`, and a separate test plan at `.sdlc/tests/<slug>/test-plan.md`. Skills read legacy locations if the canonical one is absent, but never write a parallel tree. Run `/sdlc-adopt` to consolidate.

## Templates
Every document a skill writes comes from a template in `.sdlc/templates/`. Edit those files to change the shape of what the skills produce — they are project-owned, and skills read them at generation time rather than carrying their own copies.

| Template | Produces |
|----------|----------|
| `product.md` | `.sdlc/docs/product.md` |
| `tech.md` | `.sdlc/docs/tech.md` |
| `test-strategy.md` | `.sdlc/docs/test-strategy.md` |
| `agents.md` | `AGENTS.md` (repo root) |
| `rules.md` | `.sdlc/rules.md` |
| `problem-brief.md` | `.sdlc/requirements/problem-brief.md` |
| `entity-dictionary.md` | `.sdlc/requirements/entity-dictionary.md` |
| `adr.md` | `.sdlc/docs/adr/ADR-{N}.md` |
| `architecture.md` | `.sdlc/docs/architecture.md` |
| `spec.md` | `.sdlc/specs/<slug>/spec.md` |
| `quickfix.md` | `.sdlc/specs/<slug>/quickfix-{ts}.md` |
| `review-report.md` | `.sdlc/reviews/<slug>/report-{ts}.md` |
| `drift-report.md` | `.sdlc/specs/<slug>/drift-report-{ts}.md` |

If `.sdlc/templates/` is missing, the project has not been initialised (or predates templates) — run `/sdlc-init`, which installs them without touching existing documents.

## Feature slugs
A feature directory name is the slug of the feature: lowercase; spaces/underscores to `-`; drop characters outside `[a-z0-9-]`; collapse repeated `-`; trim leading/trailing `-`. Slugs are stable — never rename once code references `.sdlc/specs/<slug>/`.

## Canonical EARS dialect
| Pattern | Template |
|---------|----------|
| Ubiquitous | The `<system>` SHALL `<response>`. |
| Event-driven | WHEN `<trigger>`, the `<system>` SHALL `<response>`. |
| State-driven | WHILE `<state>`, the `<system>` SHALL `<response>`. |
| Optional feature | WHERE `<feature is included>`, the `<system>` SHALL `<response>`. |
| Unwanted behaviour | IF `<condition>`, THEN the `<system>` SHALL `<response>`. |
| Complex | Combine, e.g. WHILE `<state>`, WHEN `<trigger>`, the `<system>` SHALL `<response>`. |

This is canonical EARS (Mavin et al.). EARS keywords are written in uppercase — that is what makes them keywords, and the validator only treats uppercase occurrences as such. Deprecated dialect found in old specs migrates as: `ALWAYS SHALL` to ubiquitous (drop ALWAYS); `AS <c> THEN SHALL` to `IF <c>, THEN ... SHALL`; `UNLESS <b> THEN SHALL <d>` to `IF NOT <b>, THEN ... SHALL <d>`; old `WHERE <state>` (state-driven) to `WHILE <state>`.

## ID & traceability scheme
- Each `spec.md` declares `**Feature Key:** <KEY>` — an uppercase token `[A-Z][A-Z0-9_-]*`, globally unique across all features. Default suggestion: the uppercased slug.
- Requirement IDs are per-feature (`REQ-001`, `NFR-001`, `UT-001`, `IT-001`, `E2E-001`, `PBT-001`) and disambiguated globally by the key.
- Source header: `IMPLEMENTS: <KEY>:REQ-001, <KEY>:NFR-002`
- Test header: `COVERS: <KEY>:REQ-002, <KEY>:UT-005, <KEY>:IT-001`
- Inline tag: `@sdlc <KEY>:REQ-003, <KEY>:REQ-004`
- IDs are immutable: never renumber or recycle. A removed requirement keeps its ID, and its text **begins** with `REMOVED ({date}) — {reason}` — the validator only treats a requirement as retired when the text starts that way.
- An NFR validated outside application code is listed once in the NFR table **and** repeated under "NFRs Validated Outside Code"; the validator treats the repeat as the same NFR (not a duplicate) and exempts it from `IMPLEMENTS:`/`COVERS:`. Naming CI in the Validated By cell does not exempt anything — CI is where validation runs, not what performs it.
- Validate with `python3 .sdlc/tools/sdlc-validate.py [--feature <slug>] [--strict]` — exit 0 clean, 1 warnings (with `--strict`), 2 errors.

## Approval tiers
- **Tier 1 — explicit per-item approval**: global / hard-to-reverse writes — `rules.md` rule modifications, ADR supersessions, entity-dictionary conflict resolutions, overwriting an existing spec, file moves.
- **Tier 2 — one batched approval**: routine first-time generation (steering docs together; requirements together; spec together).
- **Tier 3 — no approval**: read-only analysis, validator runs, and review reports (the report is the deliverable, not a source mutation).
Anything other than an affirmative ("yes" / "ok" / "approved" / "go ahead") is a change request, at any tier. Silence or a vague reply is a change request.
