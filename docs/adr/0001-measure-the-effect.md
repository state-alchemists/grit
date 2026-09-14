# ADR 0001 — Measure the effect; make the invisible visible

- **Status**: Accepted
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: measurement, dashboard, self-perception, mirror

## Context

Every intervention proposed in this design has been falsified or constrained by evidence at some point in the design process. What has never been falsified is the premise that the effect is **invisible to the person experiencing it**.

METR (2025, RCT, 16 experienced OSS developers, 246 tasks on their own mature repos): AI made them **19% slower**, while they believed it made them **20% faster**. Before the study they forecast a 24% speedup. Economists predicted 39%; ML experts 38%.

This is the one finding in the entire review that has no caveat attached to it, and it has a direct design consequence: **any component that relies on the user's own account of their proficiency or productivity is measuring nothing.**

Those products exist. The `atrophy` CLI maintains an Elo rating per skill and charts an "unaided vs AI-assisted dependence gap", but its README states plainly that AI-off is an **honor system** — it detects ten assistants, prints warnings, and never blocks. Its headline number therefore depends on the user not opening Claude. `devatrophy.com` relies on the same trust. **The category's core metric is self-reported**, which is fine for introspection and disqualifying for anything load-bearing.

## Decision

> The measurement layer is the product's foundation, not a feature. It observes what happened from instrumented signal rather than self-report, and surfaces it — the mirror is the minimum viable product, and the dashboard is the entry gate rather than a status page built last.

## Rationale

- **It is the only component with no bypass problem.** There is nothing to bypass; measurement does not ask permission and does not gate anything.
- **It is the only component with no expertise-reversal risk.** It provides no guidance and imposes no external structure, so the ADR 0002 harm case does not apply.
- **It targets the specific failure that evidence establishes.** METR's finding is not that developers are bad at this; it is that they cannot see it. A mirror is the direct answer, and no competitor closes this loop.
- **It is the substrate for everything else.** ADR 0011's routing, ADR 0010's decay, and ADR 0002's adaptive fading all read from the same measurements.

## Alternatives Considered

- **Ship the intervention first, add measurement later** — rejected. This was an earlier build order in the design (`tutorials → router → check → dashboard`) and it was wrong. A dashboard with no data is a blank screen at first run; more importantly, without measurement there is no way to tell whether any of the rest works.
- **Self-reported logging** — rejected outright. It inherits the METR gap and produces confident, wrong data. Completion is verified by executable acceptance checks, not by assertion.
- **Vendor-style adoption analytics** — rejected. DX, Jellyfish, LinearB, and Swarmia report AI adoption and throughput; none reports skill or learning.

## Consequences

- **Positive**: the honest floor is a product that stands alone — a mirror that works even if every intervention is cut.
- **Negative**: measurement without remediation decays into a guilt dashboard. This is why ADR 0003 keeps tutorials attached to real work rather than dropping them.
- **Negative**: instrumented measures are weak proxies. Acceptance rate, retention of accepted suggestions in the final diff, and prompt-to-accept latency are all confounded by task type. A single "engagement score" is a Goodhart trap and must not be built.
- **Follow-ups**: verify that the instrumented measures are available from the assistant's actual telemetry surface. Prompt-to-accept latency may be vendor-internal rather than exposed.

## Backlinks

- [ADR index](README.md)
- [ADR 0011 — Routing, deferred](0011-routing-on-a-measured-profile-deferred.md)
- [ADR 0003 — Grounded on-demand tutorials](0003-grounded-on-demand-tutorials.md)
