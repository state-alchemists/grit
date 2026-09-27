# {{PROJECT_NAME}}

## Overview
{{1-2 sentence summary}}

## Essential Commands
```bash
# Install
{{cmd}}
# Test
{{cmd}}
# Lint
{{cmd}}
# Run
{{cmd}}
# Validate SDLC traceability
python3 .sdlc/tools/sdlc-validate.py
```

## Architecture
{{Description}}

| Directory | Purpose |
|-----------|---------|
| {{source root(s)}} | Source code |
| {{test root(s)}} | Tests |
| `.sdlc/config.json` | Source/test layout, comment styles, scan overrides |
| `.sdlc/ANNOTATION.md` | Comment syntax and header placement per language |
| `.sdlc/docs/product.md` | Product vision |
| `.sdlc/docs/tech.md` | Tech decisions |
| `.sdlc/docs/test-strategy.md` | Testing approach |
| `.sdlc/CONVENTIONS.md` | Paths, EARS dialect, ID/traceability scheme |
| `.sdlc/templates/` | Templates the sdlc-* skills generate from |
| `.sdlc/rules.md` | Project invariants |
