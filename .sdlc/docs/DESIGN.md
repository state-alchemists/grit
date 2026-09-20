# Design

The principles the product is built on, and the limits it has not escaped.

**This is not the mechanism.** For how the pieces actually fit together — the three processes, the files, the data path, the invariants — read [ARCHITECTURE.md](ARCHITECTURE.md). For individual decisions and what was rejected, read [`adr/`](adr/README.md). This file is the layer above both: the rules that constrain every decision, and the things still unproven.

> An earlier version of this document also carried the on-disk layout and the data contracts. It drifted: it documented `profile.json`, `tasks.json`, `checks/` and `missions/`, none of which any code writes, and never mentioned `evidence.jsonl` or `authorship.jsonl`, which carry all the real data. Mechanism now lives in one place, because two descriptions of one system means one of them is wrong and you cannot tell which.

---

## 1. Principles

### What may be delegated to the user, and what may not

"Ask the user when unsure" is right for *configuration* and wrong for *measurement*. Stated explicitly, because otherwise it silently licenses asking the one question the whole design exists to avoid.

| Uncertainty about… | Ask the user? | Why |
|---|---|---|
| Tutorial format, depth, pace | **Yes** | Cheap to get wrong; costs annoyance only |
| Stack, repos, workflow, theme, notification style | **Yes** | Factual — the user knows their setup |
| Whether they know a concept | **No** | The one case where asking is *systematically* wrong |
| Whether the instrument predicts real work | **No** | Empirical — nobody can answer it, including the user |
| Whether a tutorial format works for them | **Partly** | Ask, then check against outcomes; the check overrules |

**The rule:** the user may configure the product. The user may not certify their own proficiency, and may not adjudicate whether the instrument is valid.

This is why the score is derived from observed events rather than declared, and why `assistance` is a coefficient the hook measures rather than a field anyone fills in.

### Preference is a prior, corrected by outcomes

Preferences are cheap to collect and easy to state wrong. People choose "just give me the answer" and are then unhappy they learned nothing — the exact failure this product exists to address.

So preference sets the **default**, and outcomes get to **overrule** it. A user who chooses "walk me through it" every time, whose justifications keep failing, is receiving a format that is not working. The system says so rather than honoring the preference silently. The correction is surfaced, never applied by stealth.

**A preference that turns the mechanism off should be visible, not silent.** "Default: just do it for me" is the user's call, but it is recorded and shown, because a configuration that quietly disables the product's only function is the METR pattern — feeling fine while capability erodes, with nothing on screen to contradict it.

### The record is append-only, and corrections do not rewrite it

Every mechanism that could edit the past has been closed, one incident at a time: the page cannot award its own judgment ([ADR 0006](adr/0006-two-credentials-per-session.md)), a verdict cannot be overwritten once cast, `earned` is derived rather than assigned, and no raw credential enters a readable file.

The general rule behind all of them: **the remedy for a wrong record is a new measurement, never an edit.** "The assistant made a mistake" is not an exemption — it is the exact case an audit trail exists for.

### The honest claim

This design **may avoid harm**. It does not claim to make anyone more skilled. Bastani et al.'s guardrailed arm was statistically indistinguishable from control; no study shows a tool producing skill *gains* over working unaided. The achievable outcome is *less erosion*.

Never promise growth. The ceiling is harm avoidance, and saying so is not modesty — a product that overclaims here is indistinguishable from the problem it is treating.

---

## 2. Scope

**In:** graded scoring from real repository work, authorship measurement, the three-gate tutorial runtime, the local daemon and dashboard, DIY handover.

**Deferred:** the onboarding battery and the router. [ADR 0009](adr/0009-graded-score-from-capped-evidence.md) removed the need for either to exist before anything can be scored — real tasks populate the profile directly. [ADR 0011](adr/0011-routing-on-a-measured-profile-deferred.md) still governs how routing must work *if* it is built.

**Built but unautomated:** tutorials. The assistant writes one against a measured gap and the runtime scores it; nothing batches, caches, shares or pre-validates them.

**Out of scope entirely:** team or hosted features, cross-user benchmarking, a tutorial library, non-coding domains, and any claim beyond harm avoidance.

Non-coding domains are excluded for a specific reason rather than a preference: everything here rests on a check that runs and either passes or fails. Project management has no `npm test`. Without an oracle the first gate degrades to *"the user says they understand"*, which is the self-report the whole design replaces — and one fictional row makes the record worthless.

---

## 3. The privacy boundary

Non-negotiable for the measurement layer ([ADR 0001](adr/0001-measure-the-effect.md)):

- **Measurement is local.** `evidence.jsonl`, `ledger.json`, `authorship.jsonl`, the dashboard and the daemon are pure localhost. The daemon binds to `127.0.0.1` and serves no cross-origin request.
- **Inference is local by default.** Concepts do not leave the machine.
- **Only tutorial generation may reach a remote model**, and only with explicit per-session consent — it is the one operation needing capability a local model may not have.

This is a hard boundary, not a preference: **a tool that profiles your weaknesses is a liability if that profile is transmitted.** It is also why `/ledger` carries opaque row ids rather than live credentials, and why `sessions.json` is mode `0600`.

---

## 4. What is still unproven

Stated here rather than left to be discovered.

1. **Does a `proven` concept predict real capability?** Nothing validates the level against later performance. This is the critical path and it is unrun — [ADR 0012](adr/0012-profile-validity-is-the-critical-path.md).
2. **The scoring constants are judgement, not measurement.** `0.5`, `0.2`, `0.30`, `0.80`, the `1.5×` cap, two-unaided-tasks — every one is a choice. They are internally consistent and satisfy the stated requirements; none is calibrated against an outcome.
3. **`assistance: partial` is self-reported.** The hook proves who typed the bytes; it cannot see whether the user read a tutorial first. This is the one soft coefficient in the model.
4. **The judgment gate is unvalidated.** A concept counts as earned only when the assistant judges the justification sound, and there is no ground truth for that judgment. It is *measurable* — judge-sound answers that later fail on the same concept would falsify it — but it has not been measured, and it is load-bearing.
5. **Retention is unmeasured.** Only behaviour at the time is observable. Nothing here measures what you can still do in a month, which is the outcome the product is named for.
6. **Sandbox tutorials may not transfer.** Passing a JavaScript exercise about token buckets is not evidence you can implement one in Go. The weights encode a guess at the gap, not a finding.
7. **Population transfer.** The mechanism evidence is from novices. The one study in the target population — METR, 16 experienced developers — measured speed, not skill.
8. **Concept names are chosen in conversation.** They are the schema, and two people naming the same idea differently produce incomparable records. Mitigated by a near-duplicate warning; not solved.

---

## 5. Where to go next

| Question | Document |
|---|---|
| How does it work? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Why is it shaped this way? | [adr/](adr/README.md) |
| How do I install and use it? | [../../README.md](../../README.md) |
| What does the assistant do? | [../../skills/grit/SKILL.md](../../skills/grit/SKILL.md) |
| What is a prop, not a feature? | [dev-fixtures.md](dev-fixtures.md) |
