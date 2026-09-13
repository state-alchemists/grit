# Architecture Decision Records

Decisions are recorded here rather than in prose design documents, so that a future reader can reconstruct *why* the design is shaped the way it is — including which options were rejected and what evidence drove the choice.

Each ADR is a point-in-time record. Statuses change; files are not deleted.

## Index

| ADR | Title | Status | What it decides |
|---|---|---|---|
| [0001](0001-route-on-measured-proficiency.md) | Route on measured proficiency, never on self-report | Accepted | How the router decides who needs a tutorial |
| [0002](0002-required-profile-with-decay.md) | Require a populated profile, and let proficiency decay | Accepted | Whether the profile is optional, and whether it expires |
| [0003](0003-withhold-guidance-by-default.md) | Withhold guidance by default; grant it narrowly and adaptively | Accepted | The intervention policy, driven by the expertise reversal effect |
| [0004](0004-measure-the-effect.md) | Measure the effect; make the invisible visible | Accepted | Measurement is the foundation, not a feature |
| [0005](0005-grounded-on-demand-tutorials.md) | Ground every tutorial in a task with a check | Accepted | What a tutorial is; no lesson library |
| [0006](0006-calibrated-battery-not-mini-games.md) | Calibrated onboarding battery, not a set of mini-games | Accepted | What the onboarding instrument is |
| [0007](0007-critical-path-battery-validity.md) | Battery validity is the critical path | Accepted | What must be tested before anything is built |
| [0008](0008-interactive-sandbox-tutorials.md) | Interactive sandbox tutorials, with a declared evidence gap | Accepted | What the tutorial runtime is, and its weaker check |
| [0009](0009-completion-via-local-daemon.md) | Completion is reported by a local daemon, and requires three gates | Accepted | How the assistant learns a tutorial was completed |
| [0010](0010-profile-derived-from-ledger.md) | The profile is derived from the ledger by the daemon | **Superseded by 0014** | What the learner model is, and what a pass may assert |
| [0011](0011-two-credentials-per-session.md) | Two credentials per session: the page reports, the assistant judges | Accepted | How gate 3 is kept out of the page's reach |
| [0012](0012-hooks-must-fail-open.md) | A hook must fail open, and the guard belongs in the registration | Accepted | Why a broken hook must never block a tool call |
| [0013](0013-dashboard-polls-files-it-does-not-push.md) | The dashboard polls files; nothing pushes | Accepted | The end-to-end data path, with a diagram |
| [0014](0014-graded-score-from-capped-evidence.md) | A graded score, derived from capped evidence | Accepted | How work becomes a level, and why it cannot be farmed |

## Reading order

- **The policy**: 0001 → 0002 → 0003. Who needs help, based on what, and how much to give.
- **The foundation**: 0004. Why measurement underpins everything above it.
- **The artifacts**: 0005 (tutorial), 0006 (battery), 0008 (tutorial runtime), 0009 (completion).
- **The model**: 0014. How work becomes a score, and why repetition stops paying.
- **The data path**: 0013. Read this to see how onboarding, the hook and the dashboard connect.
- **The availability**: 0012. Why a hook that cannot run must not stop you working.
- **The integrity**: 0011. Why one token was not enough, and what `earned` is derived from.
- **The risk**: 0007. Read this if you read only one — it names what would make the rest wrong.

## Superseded and rejected

Rejected options are documented inside the relevant ADR rather than as separate files. The two worth naming here, because they are the most tempting to reintroduce:

- **Per-mission mode selection** (*walkthrough / attempt / solve*) — the original design. Measured failing by Kapoor et al. (2025, N=885): 50% bypass, worst among those who needed the friction most. Superseded by ADR 0001's moment-not-mode trigger.
- **Step-gating at every generation** — the best-evidenced mechanism, retained only for concepts *measured* as unfamiliar. See ADR 0003.

## Consequences across all ADRs

These follow from the whole set, not from any one decision:

- **Repository work is the primary evidence source** (ADR 0014). Tutorials are a second source and their generator is still unbuilt, so today the score comes from real tasks done unaided.
- **`proven` requires two distinct unaided repository tasks.** No amount of tutorial repetition reaches it, by construction.
- **Adaptivity depends on inference**, which is unvalidated (ADR 0007). If inference fails, the design collapses to a mirror (ADR 0004).
- **The product is only as good as its routing**, which is unvalidated (ADR 0007). Interactive tutorials are the most guidance-dense artifact in the design, so routing error converts directly into expertise-reversal harm. They are what makes ADR 0007 a harder prerequisite, not a softer one.
- The honest claim is **harm avoidance, not skill gain**. Bastani et al.'s guardrailed arm was statistically indistinguishable from control. Nothing here shows a tool making anyone better than working unaided.
- **Two checks exist, with different strength.** A repository check verifies real work; a sandbox check verifies a concept in JavaScript (ADR 0008). They are recorded separately and must never be presented as equivalent.
- **Gate 3 is unreachable from the page** (ADR 0011), but its credential now has to reach the assistant out of band — printed to the daemon's stderr. That seam works and is visibly a v1 mechanism.
- **The judgment gate is the least reliable thing here.** A concept counts as earned only when a check passes, a justification is submitted, *and* the assistant judges that justification sound (ADR 0009). That third gate is a model output with no ground truth — the same weakness as ungrounded mode. If it is miscalibrated, it either blocks competent users or passes incompetent ones.
- **A tutorial pass alone can never reach `proven`** (ADR 0014). Only real work can assert strong proficiency. This is ADR 0008's weaker-oracle rule enforced in the data model — and it means an expert who passes an unfamiliar-but-adjacent tutorial stays recorded at `recall`, compounding the expert under-rating already named in §7.2.
- **The derivation rule in ADR 0010 is a model of learning, and it is unvalidated.** How evidence maps to proficiency, how confidence accumulates, and what decay does are all choices, not measurements. ADR 0007's concern now lives partly in code.
- **The profile is per-machine, not per-person.** One `~/.grit/profile.json` cannot distinguish two users on one machine, and does not follow a user across machines.
- **The daemon sees the whole ledger in plaintext.** It knows every concept the user has failed, and it stores justifications verbatim. Loopback-only and never transmitted is the entire privacy claim (Design §8) — it is a real boundary, and it is the only one.
- **Ungrounded (non-coding) work has no oracle**, so ADR 0005 cannot hold there and the guarantees are weaker. This must be documented rather than implied.
