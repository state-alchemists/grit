# Feature Spec: {{FEATURE_NAME}}

**Feature Key:** {{KEY}}

## Requirements

*Requirements cite the source `AC-*` from the problem brief. Use the canonical EARS keywords, in uppercase — no category headers needed. A retired requirement keeps its ID and its text starts with `REMOVED ({date}) — {reason}`.*

- `REQ-001` (AC-NNN): WHEN {{trigger}}, the {{system}} SHALL {{response}}.
- `REQ-002` (AC-NNN): The {{system}} SHALL {{invariant}}.
- `REQ-003` (AC-NNN): IF {{condition}}, THEN the {{system}} SHALL {{response}}.

## Non-Functional Requirements

*NFR IDs come from the problem brief — cite them, don't invent new ones here. "Validated By" names the mechanism that performs validation, not where it runs.*

| ID | Requirement | Target | Validated By |
|----|-------------|--------|--------------|
| NFR-001 | {{NFR}} | {{Target}} | {{unit test / load test / infra / manual}} |

## NFRs Validated Outside Code
*NFRs validated by infra or process, not application code. The validator exempts only these from `IMPLEMENTS:`/`COVERS:`.*
- `NFR-NNN`: {{NFR}} — validated by {{terraform module / WAF rule / SLO dashboard}}

## API Surface

*Every endpoint, method, and shape. Real HTTP status codes, real field names.*

| Method | Path | Request | Response | Auth |
|--------|------|---------|----------|------|
| {{M}} | {{P}} | {{R}} | {{S}} | {{A}} |

## Error Handling

| Condition | Status | Body |
|-----------|--------|------|
| {{Condition}} | {{Status}} | {{Response body shape}} |

## Correctness

*Only the properties that actually apply (round-trip, uniqueness, atomicity, validation, idempotency). No N/A rows.*

- **{{Property}}:** {{What the system guarantees and how it is enforced.}}

## Entities

See `.sdlc/requirements/entity-dictionary.md` — {{EntityA}} ({{key fields}}), {{EntityB}} ({{key fields}}).

### Entity Modifications
*Adding fields or changing definitions is not done silently here. Either stop and ask the user to run `/sdlc-plan` first, or — with explicit Tier-1 opt-in — update the entity dictionary in this session, then continue.*

- {{Entity}}.{{field}}: ADDED / MODIFIED / REMOVED — {{reason}}, mirrored in `.sdlc/requirements/entity-dictionary.md`.

## Test Plan

*Test naming convention: {{convention from .sdlc/docs/test-strategy.md}}*

### Unit Tests
| ID | Req | Test Name | Input | Expected |
|----|-----|-----------|-------|----------|
| UT-001 | REQ-{{N}} | test_{{unit}}_{{condition}} | {{input}} | {{expected}} |

### Integration Tests
| ID | Req | Test Name | Setup | Assertion |
|----|-----|-----------|-------|-----------|
| IT-001 | REQ-{{N}} | test_{{boundary}}_{{behaviour}} | {{setup}} | {{assert}} |

### End-to-End Tests
| ID | Req | Scenario | Steps | Expected |
|----|-----|----------|-------|----------|
| E2E-001 | REQ-{{N}} | {{scenario}} | {{steps}} | {{outcome}} |

### Property-Based Tests
*Include only if a property-testing tool is configured in tech.md or test-strategy.md. Otherwise: `N/A — no property-testing framework configured`.*

| ID | Req | Invariant | Property | Generator |
|----|-----|-----------|----------|-----------|
| PBT-001 | REQ-{{N}} | {{invariant}} | {{property}} | {{generator}} |

### Design Property Coverage
*Only the properties listed in Correctness above. No N/A rows.*

| Property | Covered By | Notes |
|----------|------------|-------|
| {{Property}} | {{UT-/IT-/PBT- ids}} | {{notes}} |

### Test Data Strategy
- **Fixtures**: {{Where fixtures live, naming convention}}
- **Synthetic data**: {{How generated, seed strategy}}
- **Cleanup**: {{How state is reset between tests}}
