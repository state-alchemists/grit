# {{PROJECT_NAME}} — Test Strategy

## Testing Levels
| Level | Scope | Tool | Target |
|-------|-------|------|--------|
| Unit | Functions/classes | {{Tool}} | {{%}} |
| Integration | Module boundaries | {{Tool}} | {{%}} |
| E2E | Critical journeys | {{Tool}} | {{N}} scenarios |

## Test Naming Convention
*The single convention `sdlc-spec` and `sdlc-implement` follow. State it explicitly so test names are deterministic.*
- {{e.g. pytest `test_<fn>_<condition>_<expected>`; JS `describe('X', () => it('does Y'))`; Go `TestFooBar`; Rust `#[test] fn foo_does_bar`}}

## CI Gates
| Gate | Trigger | Command | Blocking |
|------|---------|---------|----------|
| Lint | Pre-commit | {{Cmd}} | Yes |
| Unit Tests | Every push | {{Cmd}} | Yes |
| Traceability | Every push / PR | `python3 .sdlc/tools/sdlc-validate.py --strict` | {{Yes/No}} |

## Environments
*Include only the environments that actually exist. Do not add Staging / UAT / Canary / Sandbox unless the user said they exist.*

| Env | URL | Deploy | Data |
|-----|-----|--------|------|
| {{EnvName}} | {{URL}} | {{Auto / Manual}} | {{Real / Synthetic / Anonymized}} |

## Quality Goals
- **Unit coverage**: >= {{N}}%
- **Critical path E2E**: 100% of P0 scenarios
- **Security scanning**: {{Tool}} on every PR
