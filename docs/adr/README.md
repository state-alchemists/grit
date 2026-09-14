# Architecture Decision Records

Decisions are recorded here rather than in prose design documents, so that a future reader can reconstruct *why* the design is shaped the way it is — including which options were rejected and what evidence drove the choice.

Numbers run in reading order, not in the order the decisions were taken: everything here was decided in one design pass, so chronology carries no information and a number that tells you where to start does.

**Superseded decisions do not get their own file.** When a decision is replaced, it is folded into the ADR that replaced it, as a rejected alternative with the reason it failed. A record nobody should act on is not worth a place in the index, and the reasoning is only useful next to the decision that overruled it. Consolidated on 2026-09-14; the originals are in git history.

## Index

| ADR | Title | Status | What it decides |
|---|---|---|---|
| [0001](0001-measure-the-effect.md) | Measure the effect; make the invisible visible | Accepted | Measurement is the foundation, not a feature |
| [0002](0002-withhold-guidance-by-default.md) | Withhold guidance by default; grant it narrowly and adaptively | Accepted | The intervention policy, driven by the expertise reversal effect |
| [0003](0003-grounded-on-demand-tutorials.md) | Ground every tutorial in a task with a check | Accepted | What a tutorial is; no lesson library |
| [0004](0004-interactive-sandbox-tutorials.md) | Interactive sandbox tutorials, with a declared evidence gap | Accepted | What the tutorial runtime is, and its weaker check |
| [0005](0005-completion-via-local-daemon.md) | Completion is reported by a local daemon, and requires three gates | Accepted | How the assistant learns a tutorial was completed |
| [0006](0006-two-credentials-per-session.md) | Two credentials per session: the page reports, the assistant judges | Accepted | How gate 3 is kept out of the page's reach |
| [0007](0007-hooks-must-fail-open.md) | A hook must fail open, and the guard belongs in the registration | Accepted | Why a broken hook must never block a tool call |
| [0008](0008-dashboard-polls-files-it-does-not-push.md) | The dashboard polls files; nothing pushes | Accepted | The end-to-end data path, with a diagram |
| [0009](0009-graded-score-from-capped-evidence.md) | A graded score, derived from capped evidence | Accepted | How work becomes a level, and why it cannot be farmed |
| [0010](0010-proficiency-decays-with-inactivity.md) | Proficiency decays with inactivity | Accepted | Whether a stored level stays true |
| [0011](0011-routing-on-a-measured-profile-deferred.md) | Routing on a measured profile, and why it is deferred | Accepted — **deferred** | How the product *would* decide who needs a tutorial |
| [0012](0012-profile-validity-is-the-critical-path.md) | Profile validity is the critical path | Accepted — **unrun** | What must be tested for any of this to mean anything |

**Accepted — deferred** means the decision stands but nothing implements it. **Accepted — unrun** means it specifies a study nobody has done.

For how the system actually works — processes, files, invariants — read [ARCHITECTURE.md](../ARCHITECTURE.md) first. These records say *why*, not *what*.

## Reading order

The numbers are the reading order. If you want less than all of it:

- **Read one**: [0012](0012-profile-validity-is-the-critical-path.md). It names what would make everything else wrong.
- **Read three**: [0001](0001-measure-the-effect.md) (why measure at all) → [0009](0009-graded-score-from-capped-evidence.md) (how work becomes a level) → [0012](0012-profile-validity-is-the-critical-path.md) (why that might mean nothing).
- **Building on it**: [0006](0006-two-credentials-per-session.md), [0007](0007-hooks-must-fail-open.md) and [0008](0008-dashboard-polls-files-it-does-not-push.md) are the ones with invariants you can break by accident.

## What was rejected, and where it lives

Rejected options are documented inside the ADR that rejected them. The four most tempting to reintroduce:

- **Per-mission mode selection** (*walkthrough / attempt / solve*) — the original design. Measured failing by Kapoor et al. (2025, N=885): 50% bypass, worst among those who needed the friction most. See [0011](0011-routing-on-a-measured-profile-deferred.md).
- **Mini-games as the onboarding instrument** — a game measures ability in the game, and under-rates the experts it would then route into tutorials they do not need. See [0011](0011-routing-on-a-measured-profile-deferred.md).
- **A profile derived from tutorial completions alone** — tried and superseded: its only input was the one thing nothing generates, so the profile could never be populated. See [0009](0009-graded-score-from-capped-evidence.md).
- **XP, streaks, and an accumulated score** — a number you add to is a number you can farm. See [0009](0009-graded-score-from-capped-evidence.md).

## Consequences across all ADRs

These follow from the whole set, not from any one decision:

- **Repository work is the primary evidence source** ([0009](0009-graded-score-from-capped-evidence.md)). Tutorials are a second source that works but is unautomated — each is written by hand, per concept — so in practice most of the score comes from real tasks done unaided.
- **`proven` requires two distinct unaided repository tasks.** No amount of tutorial repetition reaches it, by construction.
- **There is no router**, so adaptivity — the thing [0002](0002-withhold-guidance-by-default.md) argues guidance should have — is not implemented. The self-completion offer is uniform, which that ADR argues against. This is the largest gap between the recorded design and the running product.
- **The product's routing would only be as good as its measurement**, which is unvalidated ([0012](0012-profile-validity-is-the-critical-path.md)). Interactive tutorials are the most guidance-dense artifact in the design, so routing error converts directly into expertise-reversal harm.
- The honest claim is **harm avoidance, not skill gain**. Bastani et al.'s guardrailed arm was statistically indistinguishable from control. Nothing here shows a tool making anyone better than working unaided.
- **Two checks exist, with different strength.** A repository check verifies real work; a sandbox check verifies a concept in JavaScript ([0004](0004-interactive-sandbox-tutorials.md)). They are recorded separately and must never be presented as equivalent.
- **Gate 3 is unreachable from the page** ([0006](0006-two-credentials-per-session.md)), but its credential has to reach the assistant out of band — printed to the daemon's stderr. That seam works and is visibly a v1 mechanism.
- **The judgment gate is the least reliable thing here.** A concept counts as earned only when a check passes, a justification is submitted, *and* the assistant judges that justification sound ([0005](0005-completion-via-local-daemon.md)). That third gate is a model output with no ground truth. If it is miscalibrated, it either blocks competent users or passes incompetent ones.
- **A tutorial pass alone can never reach `proven`** ([0009](0009-graded-score-from-capped-evidence.md)). This is [0004](0004-interactive-sandbox-tutorials.md)'s weaker-oracle rule enforced in the data model — and it means an expert who passes an unfamiliar-but-adjacent tutorial stays recorded at `recall`.
- **The scoring rule is a model of learning, and it is unvalidated.** How evidence maps to proficiency, what repetition is worth, and what decay does are all choices, not measurements. [0012](0012-profile-validity-is-the-critical-path.md)'s concern lives partly in code.
- **The record is per-machine, not per-person.** One `~/.grit/evidence.jsonl` cannot distinguish two users sharing a machine, and does not follow a user between machines.
- **The daemon sees the whole ledger in plaintext.** It knows every concept the user has failed, and it stores justifications verbatim. Loopback-only and never transmitted is the entire privacy claim ([DESIGN.md §3](../DESIGN.md)) — it is a real boundary, and it is the only one.
- **Ungrounded (non-coding) work has no oracle**, so [0003](0003-grounded-on-demand-tutorials.md) cannot hold there and the guarantees are weaker. This must be documented rather than implied.
