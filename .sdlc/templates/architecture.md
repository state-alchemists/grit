# Architecture: {{PROJECT_NAME}}

## System Context (C4 Level 1)
{{System boundary and external actors}}

## Container Diagram (C4 Level 2)
| Container | Technology | Responsibility |
|-----------|-----------|----------------|
| {{Name}} | {{Tech}} | {{Role}} |

## Component Diagram (C4 Level 3)
### {{Group}}
| Component | Responsibility | Dependencies |
|-----------|---------------|-------------|
| {{Name}} | {{Role}} | {{Deps}} |

## Key Decisions
| ADR | Title | Status |
|-----|-------|--------|
| ADR-{{N}} | {{Title}} | {{Status}} |

## Data Flow
{{How data moves between components}}

## Deployment
*Include only the environments that actually exist (per `.sdlc/docs/test-strategy.md`). Do not invent Staging / Canary.*

| Environment | Infrastructure | Strategy |
|-------------|---------------|----------|
| {{EnvName}} | {{Infra}} | {{Strategy}} |
