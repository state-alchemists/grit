# Design

The principles the product is built on, and the limits it has not escaped — the layer above both the mechanism ([architecture.md](architecture.md)) and the individual decisions ([`adr/`](adr/README.md)). It deliberately carries no file layout or data contract: those live in architecture.md alone.

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

**Deferred:** the onboarding battery and the router. [ADR 0009](adr/ADR-0009-graded-score-from-capped-evidence.md) removed the need for either to exist before anything can be scored — real tasks populate the profile directly. [ADR 0011](adr/ADR-0011-routing-on-a-measured-profile-deferred.md) still governs how routing must work *if* it is built.

**Removed:** tutorials ([ADR 0003](adr/ADR-0003-repository-work-is-the-only-evidence.md)). They were the second evidence source, and in practice they never produced any: the only path that scores is a repository task.

**Out of scope entirely:** team or hosted features, cross-user benchmarking, tutorials or lessons, **anything without an executable oracle**, and any claim beyond harm avoidance.

The exclusion is the oracle, not the domain, and stating it as "non-coding domains" was wrong in a way that cost real users. Everything here rests on a check that runs and either passes or fails. Project management has no `npm test`; without one the check degrades to *"the user says they understand"*, which is the self-report the whole design replaces, and one fictional row makes the record worthless. That argument disqualifies project management. It does not disqualify a subject merely because the person asking has no repository yet — a small practice repository with a real failing test is an oracle, whoever is sitting in front of it.

Read as "non-coding domains", the rule turned away beginners, who are the population [the novice study on the front page](../../README.md#the-problem) found were harmed most. Setting up the practice repository is scaffolding, the assistant's job; the work in it is scored like any other. One consequence is deliberate and unvalidated: two distinct unaided tasks in a practice repository reach `shipped`, though the test was written by the assistant.

---

## 3. The privacy boundary

Non-negotiable for the measurement layer ([ADR 0001](adr/ADR-0001-measure-the-effect.md)):

- **Measurement is local.** `evidence.jsonl`, `tasks.jsonl`, `authorship.jsonl`, the dashboard and the daemon are pure localhost. The daemon binds to `127.0.0.1` and serves no cross-origin request.
- **Inference is local by default.** Concepts do not leave the machine, and nothing grit runs calls a remote model.

This is a hard boundary, not a preference: **a tool that profiles your weaknesses is a liability if that profile is transmitted.** It is also why the daemon serves no cross-origin request: any local dev server could otherwise read every project you work in.

---

## 4. What is still unproven

Stated here rather than left to be discovered.

1. **Does a `shipped` concept predict real capability?** Nothing validates the level against later performance. This is the critical path and it is unrun — [ADR 0012](adr/ADR-0012-profile-validity-is-the-critical-path.md).
2. **The scoring constants are judgement, not measurement.** `0.5`, `0.30`, `0.80`, the `1.5×` cap, two-unaided-tasks — every one is a choice. They are internally consistent and satisfy the stated requirements; none is calibrated against an outcome.
3. **`assistance: partial` is self-reported.** The hook proves who typed the bytes; it cannot see how much the user was walked through. This is the one soft coefficient in the model.
4. **The justification is judged in conversation, unvalidated.** The assistant records a task only when it judges the justification sound, and there is no ground truth for that judgment. It is *measurable* — judge-sound answers that later fail on the same concept would falsify it — but it has not been measured.
5. **Retention is unmeasured.** Only behaviour at the time is observable. Nothing here measures what you can still do in a month, which is the outcome the product is named for.
6. **Practice repositories may not transfer.** A task in a repository set up for practice, against a test the assistant wrote, is not proof of the same skill in a codebase you did not choose. It scores the same, which is a guess, not a finding.
7. **Population transfer.** The mechanism evidence is from novices. The one study in the target population — METR, 16 experienced developers — measured speed, not skill.
8. **The offer itself has a bypass, and bypasses are taken by the people who need them least.** Kapoor et al. (2025, N=885) measured a three-way mode choice with a "See Solution" escape: 50% took it, and the lower-performing students took it most. That design is recorded as a rejected alternative in [ADR 0011](adr/ADR-0011-routing-on-a-measured-profile-deferred.md), and the skill still opens with a three-way choice. The defence is real but narrow — 0011 rejects routing on *what the user claims to know*, and this asks *what they want to do*, with the score measured either way — so nothing here is self-certified. What is unproven is whether that distinction survives contact with a deadline. Routing on a measured profile exists only as one rule — guidance is pre-selected on a recorded failure — and does not remove the choice.
9. **Concept names are chosen in conversation.** They are the schema, and two people naming the same idea differently produce incomparable records. Mitigated by a near-duplicate warning; not solved.

## 5. Evidence

The research the principles above rest on, in tiers by what each source can actually carry. Prior art is separated from evidence deliberately; products that occupy this space are in [product.md](product.md#alternatives--positioning). The strongest design-relevant evidence is in [ADR 0002](adr/ADR-0002-withhold-guidance-by-default.md) — in particular the **expertise reversal effect**, which says uniform scaffolding for experienced developers is contraindicated.

### Tier 1 — Headline: the harm is real, causal, and invisible to the person experiencing it

**Bastani et al. (2025), PNAS 122(26)** — [pnas.org](https://www.pnas.org/doi/10.1073/pnas.2422633122) · [full text PDF](https://hamsabastani.github.io/education_llm.pdf) · correction [PNAS 2518204122](https://www.pnas.org/doi/10.1073/pnas.2518204122)

Field experiment in high school mathematics, ~1,000 students, three arms (control / GPT Base / GPT Tutor). Unrestricted GPT access produced **−17% on an unassisted exam**; the guardrailed tutor arm was **statistically indistinguishable from control**. Causal, peer-reviewed, and the strongest result in this document. It says guardrails are the active ingredient. *Read the correction before citing exact figures — it has not been reviewed here.*

**METR (2025)** — [arxiv.org/abs/2507.09089](https://arxiv.org/abs/2507.09089)

RCT, 16 experienced OSS developers, 246 tasks on their own mature repos (avg. 5 years' prior experience there). AI **increased completion time by 19%**; developers estimated afterward that it had reduced it by 20%. Economists predicted a 39% speedup; ML experts 38%. Robust across 20 setting properties examined. *Preprint.* This is the best available argument that the effect is **not self-detectable** — which is why Grit's ledger is measured, not self-reported.

**Shen & Tamkin (2026)** — [arxiv.org/abs/2601.20245](https://arxiv.org/abs/2601.20245)

Randomized experiments, **52 novice developers** learning an unfamiliar async library (Trio). AI assistance **impaired conceptual understanding, code reading, and debugging, without significant average efficiency gains**; full delegation traded learning for speed.

*Caveats, correcting our earlier overstatement: the abstract describes participants as "novice developers," not professionals — they were recruited via a crowd-work platform and screened for >1 year of Python and no prior Trio exposure. The paper is also widely summarized as identifying "three of six interaction patterns that preserve learning"; those clusters have n = 2, 3, 7, and 4. That is a hypothesis-generating observation, not a validated result, and it should not be cited as one. Preprint.*

### Tier 2 — Mechanism: what works, and how optional guardrails fail

**Kazemitabaar et al. (IUI 2025)** — [arxiv.org/abs/2410.08922](https://arxiv.org/abs/2410.08922)

Compared **seven** cognitive-engagement techniques for keeping learners engaged with AI-generated code. N=82 between-subjects, N=42 within-subjects; evaluated on friction, transfer to isomorphic tasks *without* AI, and alignment of perceived vs. actual ability. **Winner: step-by-step interactive dialog — the learner states what the code needs to do at each stage before it is revealed.** Per-step rather than per-mission, and with no bypass button. *Population is novice programmers — see the population caveat below and §4, item 7.*

**Kapoor et al. (2025)** — [arxiv.org/abs/2504.11146](https://arxiv.org/abs/2504.11146)

Optional guardrails in a large intro programming course, N=885. **50% used the "See Solution" bypass at least once; 14% used it on all three problems; lower-performing students bypassed more, and closer to deadlines.** Motivations: needing help, time pressure, lack of self-regulation, curiosity.

**This is evidence *against* Grit's original default design, not for it.** It is a measurement of the failure mode that voluntary guardrails invite, and it is why per-mission mode selection was abandoned — see [ADR 0011](adr/ADR-0011-routing-on-a-measured-profile-deferred.md).

### Tier 3 — Model: why rational adoption still traps you

**Caosun & Aral (2026)** — [arxiv.org/pdf/2604.03501](https://arxiv.org/pdf/2604.03501)

A formal model, not an experiment: rational AI adoption can *lower* long-run productivity, because practice-displacing offloading erodes skill — an "augmentation trap" producing permanent skill stratification. Proposes "skill preservation" workflows as the countermeasure. The phrase "practice-displacing" is verbatim. *Preprint; theoretical.*

### The strongest opposing result — cited deliberately

**Cui et al., Management Science (2025)** — [pubsonline.informs.org](https://pubsonline.informs.org/doi/10.1287/mnsc.2025.00535)

Three field RCTs, **4,867 developers**, **+26% task completion**, with gains concentrated in *less-experienced* developers. AI measurably helps throughput, and helps most where skill is thinnest.

An evidence section that cites only harm reads as advocacy. This is the honest counterweight, and it sharpens rather than weakens the claim: **throughput and skill retention are separate outcomes.** Cui et al. measured one. Bastani et al. measured the other and found it can go negative. Grit exists because nobody measures the second one in a coding assistant.

### Design precedent only — no outcome data, not evidence

CodeHelp, CodeAid, PeteChat, Groher et al. These are prior art for how guardrailed assistants are built. None supply an outcome result that should be weighed.

### Dropped

**Gerlich (2025)** — previously cited here via [apa.org](https://www.apa.org/monitor/2026/07-08/ai-job-skills-thinking) as evidence of cognitive harm. It is a **correlational self-report** study with a published MDPI correction, and cannot carry weight in a design argument. If cited at all, cite [Societies 15(1), 6](https://www.mdpi.com/2075-4698/15/1/6) directly — never the APA secondary.

### Practitioner view
Addy Osmani, ["Avoiding Skill Atrophy in the Age of AI"](https://addyo.substack.com/p/avoiding-skill-atrophy-in-the-age)

### Verification notes

- **Preprints:** Shen & Tamkin (arXiv:2601.20245), METR (arXiv:2507.09089), and Caosun & Aral (arXiv:2604.03501) are preprints. Treat effect sizes as provisional.
- **Population mismatch — the most important caveat here.** The mechanism evidence (Kazemitabaar, novices) and the skill-formation evidence (Shen & Tamkin, 52 novices via crowd-work) are both drawn from **learners, not working developers on their own repos**. The only study in Grit's actual target population is METR — 16 experienced OSS developers — and it measured *speed*, not skill. Every claim about skill retention in experienced developers is an extrapolation. Do not present it otherwise.
- **Corrected since first draft:** (a) Shen & Tamkin participants are *novice developers*, not professionals; (b) their six interaction clusters have n = 2, 3, 7, 4 and are not a validated finding; (c) "Iris" was a first author's name (Groher), not a tool; (d) CodeHelp's "95%" is 95% of 45 respondents on an extra-credit survey about interest in future courses; (e) Kapoor et al. was originally cited *in support of* optional guardrails — it is evidence against them.
- **Paying, not yet read:** the [Bastani correction](https://www.pnas.org/doi/10.1073/pnas.2518204122) exists (PNAS 403s on automated fetch). Verify before citing exact figures.
- **Fetch limits:** pnas.org and mdpi.com blocked automated fetch and were verified via search snippets and secondary full text.

**A citation is not verified until its abstract has been read.** Every correction above came from a first pass that compiled citations from titles and search snippets — Kapoor et al. was cited from the phrase "optional guardrails" without reading that the study measures their failure.

---

## 6. Where to go next

| Question | Document |
|---|---|
| How does it work? | [architecture.md](architecture.md) |
| Why is it shaped this way? | [adr/](adr/README.md) |
| How do I install and use it? | [../../README.md](../../README.md) |
| What does the assistant do? | [../../skills/grit/SKILL.md](../../skills/grit/SKILL.md) |
| What else exists, and where does Grit fit? | [product.md](product.md) |
| What is a prop, not a feature? | [dev-fixtures.md](dev-fixtures.md) |
