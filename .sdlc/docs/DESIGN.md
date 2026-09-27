# Design

The principles the product is built on, and the limits it has not escaped — the layer above both the mechanism ([ARCHITECTURE.md](ARCHITECTURE.md)) and the individual decisions ([`adr/`](adr/README.md)). It deliberately carries no file layout or data contract: those live in ARCHITECTURE.md alone.

---

## 1. Principles

### What may be delegated to the user, and what may not

"Ask the user when unsure" is right for *configuration* and wrong for *measurement*. Stated explicitly, because otherwise it silently licenses asking the one question the whole design exists to avoid.

| Uncertainty about… | Ask the user? | Why |
|---|---|---|
| How much explanation, and at what pace | **Yes** | Cheap to get wrong; costs annoyance only |
| Stack, repos, workflow, theme, notification style | **Yes** | Factual — the user knows their setup |
| Whether they know a concept | **No** | The one case where asking is *systematically* wrong |
| Whether the instrument predicts real work | **No** | Empirical — nobody can answer it, including the user |
| Whether being walked through it works for them | **Partly** | Ask, then check against outcomes; the check overrules |

**The rule:** the user may configure the product. The user may not certify their own proficiency, and may not adjudicate whether the instrument is valid.

This is why the score is derived from observed events rather than declared, and why `assistance` is a coefficient the hook measures rather than a field anyone fills in.

### Preference is a prior, corrected by outcomes

Preferences are cheap to collect and easy to state wrong. People choose "just give me the answer" and are then unhappy they learned nothing — the exact failure this product exists to address.

So preference sets the **default**, and outcomes get to **overrule** it. A user who chooses "walk me through it" every time, whose justifications keep failing, is receiving a format that is not working. The system says so rather than honoring the preference silently. The correction is surfaced, never applied by stealth.

**A preference that turns the mechanism off should be visible, not silent.** "Default: just do it for me" is the user's call, but it is recorded and shown, because a configuration that quietly disables the product's only function is the METR pattern — feeling fine while capability erodes, with nothing on screen to contradict it.

**This is the setting, never the session.** The two look like one rule and are not, and reading them as one produced a live contradiction with the skill for as long as neither was implemented. Declining a task is measured *not at all* — no authorship, no evidence, no task verdict — because measuring someone who opted out is surveillance. The standing configuration is a different object: it is not work, it is what the product is doing to itself, and it belongs on screen. `serve.py`'s `_compose_config_notices` derives both from what is already there and stores neither; a preferences key holding the answer would be a second place for it to live.

### The record is append-only, and corrections do not rewrite it

Every mechanism that could edit the past has been closed, one incident at a time: evidence, task verdicts and authorship are append-only files, a level is derived rather than stored, and a re-verified task adds a row rather than replacing one.

The general rule behind all of them: **the remedy for a wrong record is a new measurement, never an edit.** "The assistant made a mistake" is not an exemption — it is the exact case an audit trail exists for.

### The honest claim

This design **may avoid harm**. It does not claim to make anyone more skilled. Bastani et al.'s guardrailed arm was statistically indistinguishable from control; no study shows a tool producing skill *gains* over working unaided. The achievable outcome is *less erosion*.

Never promise growth. The ceiling is harm avoidance, and saying so is not modesty — a product that overclaims here is indistinguishable from the problem it is treating.

---

## 2. Scope

**In:** graded scoring from real repository work, authorship measurement, per-task verdicts, the local daemon and dashboard, DIY handover.

**Deferred:** the onboarding battery and the router. [ADR 0009](adr/0009-graded-score-from-capped-evidence.md) removed the need for either to exist before anything can be scored — real tasks populate the profile directly. [ADR 0011](adr/0011-routing-on-a-measured-profile-deferred.md) still governs how routing must work *if* it is built.

**Removed:** tutorials ([ADR 0003](adr/0003-repository-work-is-the-only-evidence.md)). They were the second evidence source, and in practice they never produced any: the only path that scores is a repository task.

**Out of scope entirely:** team or hosted features, cross-user benchmarking, tutorials or lessons, **anything without an executable oracle**, and any claim beyond harm avoidance.

The exclusion is the oracle, not the domain, and stating it as "non-coding domains" was wrong in a way that cost real users. Everything here rests on a check that runs and either passes or fails. Project management has no `npm test`; without one the check degrades to *"the user says they understand"*, which is the self-report the whole design replaces, and one fictional row makes the record worthless. That argument disqualifies project management. It does not disqualify a subject merely because the person asking has no repository yet — a small practice repository with a real failing test is an oracle, whoever is sitting in front of it.

Read as "non-coding domains", the rule turned away beginners, who are the population [the novice study on the front page](../../README.md#the-problem) found were harmed most. Setting up the practice repository is scaffolding, the assistant's job; the work in it is scored like any other. One consequence is deliberate and unvalidated: two distinct unaided tasks in a practice repository reach `shipped`, though the test was written by the assistant.

---

## 3. The privacy boundary

Non-negotiable for the measurement layer ([ADR 0001](adr/0001-measure-the-effect.md)):

- **Measurement is local.** `evidence.jsonl`, `tasks.jsonl`, `authorship.jsonl`, the dashboard and the daemon are pure localhost. The daemon binds to `127.0.0.1` and serves no cross-origin request.
- **Inference is local by default.** Concepts do not leave the machine, and nothing grit runs calls a remote model.

This is a hard boundary, not a preference: **a tool that profiles your weaknesses is a liability if that profile is transmitted.** It is also why the daemon serves no cross-origin request: any local dev server could otherwise read every project you work in.

---

## 4. What is still unproven

Stated here rather than left to be discovered.

1. **Does a `shipped` concept predict real capability?** Nothing validates the level against later performance. This is the critical path and it is unrun — [ADR 0012](adr/0012-profile-validity-is-the-critical-path.md).
2. **The scoring constants are judgement, not measurement.** `0.5`, `0.30`, `0.80`, the `1.5×` cap, two-unaided-tasks — every one is a choice. They are internally consistent and satisfy the stated requirements; none is calibrated against an outcome.
3. **`assistance: partial` is self-reported.** The hook proves who typed the bytes; it cannot see how much the user was walked through. This is the one soft coefficient in the model.
4. **The justification is judged in conversation, unvalidated.** The assistant records a task only when it judges the justification sound, and there is no ground truth for that judgment. It is *measurable* — judge-sound answers that later fail on the same concept would falsify it — but it has not been measured.
5. **Retention is unmeasured.** Only behaviour at the time is observable. Nothing here measures what you can still do in a month, which is the outcome the product is named for.
6. **Practice repositories may not transfer.** A task in a repository set up for practice, against a test the assistant wrote, is not proof of the same skill in a codebase you did not choose. It scores the same, which is a guess, not a finding.
7. **Population transfer.** The mechanism evidence is from novices. The one study in the target population — METR, 16 experienced developers — measured speed, not skill.
8. **The offer itself has a bypass, and bypasses are taken by the people who need them least.** Kapoor et al. (2025, N=885) measured a three-way mode choice with a "See Solution" escape: 50% took it, and the lower-performing students took it most. That design is recorded as a rejected alternative in [ADR 0011](adr/0011-routing-on-a-measured-profile-deferred.md), and the skill still opens with a three-way choice. The defence is real but narrow — 0011 rejects routing on *what the user claims to know*, and this asks *what they want to do*, with the score measured either way — so nothing here is self-certified. What is unproven is whether that distinction survives contact with a deadline. Routing on a measured profile exists only as one rule — guidance is pre-selected on a recorded failure — and does not remove the choice.
9. **Concept names are chosen in conversation.** They are the schema, and two people naming the same idea differently produce incomparable records. Mitigated by a near-duplicate warning; not solved.

---

## 5. Where to go next

| Question | Document |
|---|---|
| How does it work? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Why is it shaped this way? | [adr/](adr/README.md) |
| How do I install and use it? | [../../README.md](../../README.md) |
| What does the assistant do? | [../../skills/grit/SKILL.md](../../skills/grit/SKILL.md) |
| What is a prop, not a feature? | [dev-fixtures.md](dev-fixtures.md) |
