# ADR 0005 — Completion is reported by a local daemon, and requires three gates

- **Status**: Accepted
- **Date**: 2026-09-13
- **Deciders**: Go Frendi
- **Context tags**: completion, daemon, ledger, verification, integrity

## Context

ADR 0004 established that tutorials are interactive JavaScript sandboxes. It left open how the assistant learns that a tutorial was completed — a gap the prototype makes visible: the template's "I recorded it" message writes nothing, and its pass state lives in a `localStorage` key scoped to the file path. Close the tab and the evidence is gone.

Four mechanisms were considered. One constraint decides among them: **a browser page cannot write to the filesystem, and a `file://` origin is opaque, so `fetch()` to a local server is blocked by CORS unless that server opts in.** With no daemon, browser security forecloses both the file-write and the callback paths. There is no workaround; the sandbox is working as designed.

The four options:

| | Mechanism | Trustworthy? | Automatic? |
|---|---|---|---|
| **A** | Local daemon over loopback | Yes — authenticated write | Yes |
| **B** | Page writes a file | No — no filesystem access | n/a |
| **C** | Clipboard handoff | Yes — signed token | No — one paste |
| **D** | User says "done" | **No** — self-report | Yes |

D is the mechanism ADR 0011 exists to eliminate. B is foreclosed by the browser. The real choice is between A and C, and A wins on the property that matters: **the completion reaches the ledger without the user having to remember to report it**, which is the METR failure mode — a person cannot be relied on to notice or to report accurately.

## Decision

> The assistant ships a local daemon (`grit serve`) that owns the tutorial session and the ledger. The page reports over loopback with an authenticated write. **A concept counts as earned only when all three gates pass: the executable check, the justification submission, and the assistant's judgment that the justification is sound.**

## Rationale

- **A daemon makes the write authenticated.** The page receives a single-use token minted at launch and scoped to one concept. A hand-edited `ledger.json` therefore *can* claim a pass — the daemon cannot stop someone editing its own file — but the daemon can tell whether a write came through the session it issued, and record that. Integrity becomes observable rather than assumed.
- **The daemon is also required for local inference** (Design §8). The battery and probes run against a local model; the daemon is the natural host. This is not new infrastructure invented for reporting — it is the component the privacy boundary already implied.
- **Three gates, because the check alone cannot distinguish knowing from guessing.** A user can iterate until green without understanding the concept. The justification is what separates them, and ADR 0002 already places feedback *after* the check — so the judgment is where it was always going to be.
- **The judgment gate is a measurement, so it is not delegated.** The user may configure the product; the user may not certify their own proficiency (ADR 0011). "I understood it" is the self-report that gate exists to replace.

## Alternatives Considered

- **Clipboard handoff** — rejected as the primary path. It works offline with no daemon and is honest about what is reported, but it requires the user to remember a step after finishing, and the population most likely to skip it is the one under time pressure. **Retained as a fallback** for environments where the daemon cannot run.
- **Trust the user ("done")** — rejected. This is option D, the METR pattern: feeling fine while the ledger drifts from reality, with nothing on screen to contradict it.
- **Page writes a file** — rejected as impossible. A browser page has no filesystem access.
- **Two gates (check + submitted justification, unjudged)** — rejected. It makes completion a fact about *typing*, not understanding: a user could submit "because it works" and be logged as having earned the concept.

## Consequences

- **Positive**: completion is automatic and auditable. The user does not have to report, and the ledger records how it was written.
- **Positive**: the daemon root (`GET /`) is a browsable index of tutorials and ledger state, so "what do I have, and where did I leave it" is answerable without reading JSON. A daemon that 404s at `/` reads as broken rather than as an empty state.
- **Negative**: **`grit serve` is now a required component**, and the product is no longer a pure skill with no running process. The template remains offline for *working*; the daemon is needed only for *reporting*. Still a real cost, and it contradicts the earlier "self-contained" framing of ADR 0004 — that framing applied to the tutorial artifact, not the system.
- **Negative**: **the tutorials directory starts empty and the daemon ships nothing to fill it.** First-run experience is an empty index and a copy-paste instruction. This is a direct tension with ADR 0003 (no lesson library): the runtime is demonstrable only once a tutorial has been written, which means a new user cannot evaluate it until the assistant authors one for them.
- **Negative**: the judgment gate makes the assistant an **examiner**, and a wrong judgment either blocks a competent user or passes an incompetent one. Judging free-text answers for soundness is the least reliable thing in this design, and it is now load-bearing.
- **Negative**: the judgment is a model output with no ground truth. Unlike the sandbox check, there is nothing to verify it against — the same limitation that weakens ungrounded mode (Design §5).
- **Follow-ups**: the judgment must be **calibrated against the user's later performance** — if judgments marked sound correlate with later failure on the same concept, the examiner is wrong, and that is measurable. This belongs in Q1.
- **Follow-ups**: the clipboard fallback should ship, so the daemon is an optimisation rather than a hard dependency.

## Backlinks

- [ADR index](README.md)
- [ADR 0011](0011-routing-on-a-measured-profile-deferred.md) · [0002](0002-withhold-guidance-by-default.md) · [0001](0001-measure-the-effect.md) · [0004](0004-interactive-sandbox-tutorials.md)
