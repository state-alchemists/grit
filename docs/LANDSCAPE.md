# Landscape — What Exists, and Where Grit Fits

Survey of products and research adjacent to Grit, with an honest account of what is already solved and what is not. Verdict codes: **EXACT** (all four of Grit's steps), **PARTIAL** (2–3 steps), **ADJACENT** (1 step or neighbouring idea).

**Bottom line (corrected): products DO exist in this space, and an earlier version of this document wrongly said they did not.** The individual-facing anti-atrophy tools were missed on the first pass — see [§6a](#6a-correction--products-do-occupy-this-space) for Chestnut, `atrophy`, Lathe, and devatrophy.com. The opening is not "nobody built this"; it is that **nobody closes the measurement loop or enforces the AI-off signal.**

The strongest design-relevant evidence is not here but in [ADR 0003](adr/0003-withhold-guidance-by-default.md) — in particular the **expertise reversal effect**, which says uniform scaffolding for experienced developers is contraindicated.

---

## 1. Gamified AI coding agents

### HagiCode — PARTIAL
[hagicode.com](https://hagicode.com/en-US/) · [product overview](https://docs.hagicode.com/en-US/product-overview/) · [gamification design](https://docs.hagicode.com/en-US/blog/2026-03-16-gamifying-ai-coding/) · [Steam](https://store.steampowered.com/app/4625540/Hagicode/)

An agentic coding workspace (desktop, Docker, Microsoft Store) that wraps 13 agent CLIs. It has an OpenSpec plan workflow with human-gated validation — Review → Scaffold → Spec → Design → Tasks → Validate → Apply → Archive — so steps 1 and 2 of Grit's flow are present. The gamification is built around **Heroes** (the AI assistants) in **Dungeons** (workflows: proposal.generate, proposal.execute, proposal.archive), with XP, level stages (`rookieSprint` ≤100 → `legendMarathon` >700), achievements, and daily Battle Reports.

**The divergence:** HagiCode gamifies the *agents'* activity. The AI levels up while the human watches. There is no tutorial, no do-it-yourself mode, and the task decomposition is sized for throughput, not learning.

*Caveat: gamification internals come from HagiCode's own documentation and marketing. Verify by using it.*

### vantage-quest — PARTIAL (weak)
[pkg.go.dev](https://pkg.go.dev/github.com/KOLLECTABLES/vantage-quest/quest) (v0.1.0)

A Go library explicitly building a "gamified quest tracking system for agentic coding workflows": Quests → Objectives → Steps, XP with difficulty multipliers, achievements, streaks, and anti-cheat guardrails (steps must be >10 chars, blocking lazy "do it" steps). It models the mission structure but is a data layer — no tutorial, no AI solver, no modes.

*Note: the GitHub web page 404s; the module is published and indexed on pkg.go.dev.*

### Agent Quest — ADJACENT
[github.com/FulAppiOS/Agent-Quest](https://github.com/FulAppiOS/Agent-Quest) — MIT, ~137 stars

A real-time 2D medieval-village dashboard where each running Claude Code or Codex session is a walking hero (Read→Library, Edit→Forge, Bash→Arena). Pure monitoring visualisation.

### `gh dungeons` — ADJACENT
[github.blog](https://github.blog/ai-and-ml/github-copilot/dungeons-desktops-building-a-procedurally-generated-roguelike-with-github-copilot-cli/)

Turns a repo into a playable roguelike. A viral demo, not a workflow.

---

## 2. Gamified task managers (tasks → quests → XP)

### Task Quest (Sourcelogic) — PARTIAL
[sourcelogic.ai](https://www.sourcelogic.ai/)

Epics → Quests → Tasks, XP by difficulty, streaks, leaderboard, and an **AI Quest Planner** that takes a goal in chat and generates the full breakdown. Strong on Grit's steps 1 and 2 for *generic* tasks. No code execution, no coding tutorial, no AI-solves-it mode.

### MainQuest — ADJACENT
[mainquest.net](https://www.mainquest.net/)

RPG habit app: 16 classes, XP, HP, streaks, focus timer. Android/iOS/web. No AI planner visible, no code context.

### MagicTask — ADJACENT
[magictask.io](https://www.magictask.io/) — team task management with XP, realms, dungeons.

**Unverified:** "QuestMind" and "Daily Quests" appear only in listicles and student papers. I could not confirm a distinct shipping product under either name. Do not cite them as real.

---

## 3. Coding education with AI tutors

### Boot.dev — PARTIAL
[boot.dev](https://www.boot.dev/)

The closest match on steps 3 and 4 *as learning*: lesson → challenge structure with XP and leaderboards, and an AI tutor named **Boots** that uses the Socratic method — deliberately supplying targeted questions and hints instead of answers. Best real precedent for the pedagogy. But it is a fixed curriculum, not generated from a plan you agreed, and the AI never completes the task for you.

### Claude Code `/output-style learning` — PARTIAL
[zdnet.com](https://www.zdnet.com/article/claude-can-teach-you-how-to-code-now-and-more-how-to-try-it/) · [tessl.io](https://tessl.io/blog/claude-code-now-lets-you-customize-its-communication-style)

Pauses and leaves `#TODO` sections for the human to fill in. `/output-style explanatory` explains rationale and trade-offs. Claude.ai has a Socratic "Learning" preset. Since the default mode lets Claude write everything, the do-it-yourself / let-AI-do-it axis already exists *at the assistant level*. Missing: plan→mission decomposition, per-mission tutorials, gamified tracking.

### ChatGPT Study Mode — PARTIAL (step 4 only)
[openai.com](https://openai.com/index/chatgpt-study-mode/) · [FAQ](https://help.openai.com/en/articles/11780217-chatgpt-study-mode-faq)

Free Socratic tutoring: guiding questions, hints, scaffolding, knowledge checks. Reported to give the direct answer if pushed repeatedly — effectively "learn it, or let it tell you". General-purpose; not coding-mission structured.

### Others — ADJACENT
[Codédex](https://www.codedex.io/) (character creation, XP, badges) · [Exercism](https://exercism.org/) (83 language tracks, human + AI mentoring) · [Codewars](https://www.codewars.com/) (kata, ranks, solution comparison) · [CodinGame](https://www.codingame.com/) (games and bot programming) · [Scrimba](https://scrimba.com/) (interactive screencasts) · Codecademy, Treehouse, SoloLearn

All gamify learning well. None attach tutorials to *your* repo work, and none offer an AI-auto-solve escape hatch alongside the tutorial.

*Codefetch note: Exercism and Scrimba homepages returned 403 / JS-only bodies. Their capabilities are described from search snippets, not primary text.*

### SkillTree — ADJACENT
[skilltreeplatform.dev](https://skilltreeplatform.dev/overview/) · [github.com/NationalSecurityAgency/skills-service](https://github.com/NationalSecurityAgency/skills-service) · [projectskilltree.com](https://www.projectskilltree.com/)

Two distinct things under one name. The NSA's open-source skills-service adds skill trees and levels to *existing* training apps — relevant as a precedent for the progression model. Project SkillTree is an unrelated consumer self-improvement app. Neither is an AI coding tool.

---

## 4. The guardrail-AI research vein

This is the richest and most rigorous area, and the one Grit builds on directly.

### CodeHelp — PARTIAL
[codehelp.app](https://codehelp.app/) · [paper](https://dl.acm.org/doi/fullHtml/10.1145/3631802.3631830) · [PDF](https://arxiv.org/pdf/2308.06921)

The canonical guardrailed LLM teaching assistant. A multi-prompt pipeline — sufficiency check → main response → **code-removal prompt** — refuses to reveal complete solutions, plus an instructor-defined "avoid set". Deployed with 52 students over 12 weeks. Grit's step 4 owes its shape to this. No plan/mission structure, no auto-solve option, no gamification.

*Reporting note: the often-quoted "95% wanted to use it again" is 95% of 45 respondents on an extra-credit-incentivized survey, asked about interest in future courses — not a completion or learning outcome. CodeHelp is **design precedent, not evidence**.*

### CodeAid — PARTIAL
[arxiv.org/html/2401.11314v2](https://arxiv.org/html/2401.11314v2) · [CHI 2024](https://dl.acm.org/doi/10.1145/3613904.3642773)

Classroom LLM assistant balancing student and educator needs, giving explanation, pseudo-code, and debugging help rather than final code.

### Others in the vein — PARTIAL
- **Groher et al.** — [arxiv.org/html/2604.11836](https://arxiv.org/html/2604.11836) — course-aware tutor avoiding full solutions, offering hints and counter-questions. *(Previously cited here as "Iris": that is the first author's given name — Iris Groher, JKU Linz — not the tool. The tool is unnamed. An unrelated AI tutor also called Iris exists, which makes the mis-citation doubly confusing.)*
- **PeteChat / "Tutor, Not Solver"** — [arxiv.org/html/2606.09845](https://arxiv.org/html/2606.09845) — guardrailed higher-ed assistant using Socratic questioning.
- **Lee et al., CHI 2025** — further design precedent in the same space.

---

## 5. Evidence

Presented in tiers by what each source can actually carry. Prior art is separated from evidence deliberately.

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

Compared **seven** cognitive-engagement techniques for keeping learners engaged with AI-generated code. N=82 between-subjects, N=42 within-subjects; evaluated on friction, transfer to isomorphic tasks *without* AI, and alignment of perceived vs. actual ability. **Winner: step-by-step interactive dialog — the learner states what the code needs to do at each stage before it is revealed.** Per-step rather than per-mission, and with no bypass button. *Population is novice programmers — see the transfer caveat in §7.*

**Kapoor et al. (2025)** — [arxiv.org/abs/2504.11146](https://arxiv.org/abs/2504.11146)

Optional guardrails in a large intro programming course, N=885. **50% used the "See Solution" bypass at least once; 14% used it on all three problems; lower-performing students bypassed more, and closer to deadlines.** Motivations: needing help, time pressure, lack of self-regulation, curiosity.

**This is evidence *against* Grit's original default design, not for it.** It is a measurement of the failure mode that voluntary guardrails invite, and it is why DESIGN.md §7 was rewritten.

### Tier 3 — Model: why rational adoption still traps you

**Caosun & Aral (2026)** — [arxiv.org/pdf/2604.03501](https://arxiv.org/pdf/2604.03501)

A formal model, not an experiment: rational AI adoption can *lower* long-run productivity, because practice-displacing offloading erodes skill — an "augmentation trap" producing permanent skill stratification. Proposes "skill preservation" workflows as the countermeasure. The phrase "practice-displacing" is verbatim. *Preprint; theoretical.*

### The strongest opposing result — cited deliberately

**Cui et al., Management Science (2025)** — [pubsonline.informs.org](https://pubsonline.informs.org/doi/10.1287/mnsc.2025.00535)

Three field RCTs, **4,867 developers**, **+26% task completion**, with gains concentrated in *less-experienced* developers. AI measurably helps throughput, and helps most where skill is thinnest.

A landscape document that cites only harm reads as advocacy. This is the honest counterweight, and it sharpens rather than weakens the claim: **throughput and skill retention are separate outcomes.** Cui et al. measured one. Bastani et al. measured the other and found it can go negative. Grit exists because nobody measures the second one in a coding assistant.

### Design precedent only — no outcome data, not evidence

CodeHelp, CodeAid, PeteChat, Groher et al. These are prior art for how guardrailed assistants are built. None supply an outcome result that should be weighed.

### Dropped

**Gerlich (2025)** — previously cited here via [apa.org](https://www.apa.org/monitor/2026/07-08/ai-job-skills-thinking) as evidence of cognitive harm. It is a **correlational self-report** study with a published MDPI correction, and cannot carry weight in a design argument. If cited at all, cite [Societies 15(1), 6](https://www.mdpi.com/2075-4698/15/1/6) directly — never the APA secondary.

### Practitioner view
Addy Osmani, ["Avoiding Skill Atrophy in the Age of AI"](https://addyo.substack.com/p/avoiding-skill-atrophy-in-the-age)

---

## 6. The gaps Grit fills

Four parts of the concept have **no existing product**:

1. **Missions generated from a mutually-approved plan, specifically to grow the human's skill.** HagiCode and Claude Code plan mode both give plan→approval→execution, but decompose for *task throughput*, not skill-building.
2. **A per-mission optional tutorial attached to live, real-repo work.** Tutorials exist only inside fixed curricula (Boot.dev, Codecademy). Plan-derived, per-mission tutorials for your own codebase: **Chestnut does this** — see §6a, which corrects this section.
3. **The explicit three-way choice — follow tutorial / attempt directly / let AI auto-solve — as a first-class, per-mission UI.** The pieces exist on opposite sides of the fence (Socratic hint modes on one side, auto-solve agents on the other), but no product presents them as one selectable triad.
4. **Gamification of the *human developer's* skill progression during real work.** HagiCode gamifies the agents; Task Quest and MainQuest gamify generic tasks; none gamify the human coder's missions tied to real commits.

### Nearest neighbours, summarized

| Product | Closest to Grit in | Diverges by |
|---------|-------------------|-------------|
| Chestnut | gap detection → micro-courses | no measurement loop; see §6a |
| `atrophy` CLI | Elo per skill + dependence gap | measures without teaching; honor-system |
| HagiCode | plan → gamified quests | gamifies the agents, no learning modes |
| Claude Code learning mode | answer-withholding + auto-solve escape | no plan→mission structure |
| Boot.dev "Boots" | Socratic tutor inside missions | fixed curriculum, not your repo |
| Task Quest AI planner | goal → quest decomposition | generic tasks, no code |
| CodeHelp | deliberate solution-withholding | no missions, no gamification |
| Kapoor et al. AI TA | *the exact mode-choice + bypass design* | it is a **cautionary** precedent, see §5 |

The Kapoor row is the uncomfortable one: the closest published match to Grit's original three-mode design is a study of that design failing at scale.

---

## 6a. Correction — products DO occupy this space

**The earlier claim in this document that no product occupies the concept was wrong.** It came from a first-pass survey that missed the individual-facing tools entirely. Verified in a second pass:

| Product | What it is | Enforcement | Published evidence |
|---|---|---|---|
| **[Chestnut](https://chestnut.so)** | "The antidote to AI-induced skill atrophy." MCP hook into your coding agent infers gaps from shipped code, generates micro-courses, maintains a skillset model | None | **None** |
| **[`atrophy` CLI](https://github.com/ashutosh-rath02/atrophy)** | MIT. Spaced drills with AI off, auto-graded, **Elo per skill**, charts unaided-vs-assisted "dependence gap" | **Honor system** — detects 10 assistants, warns, never blocks | None |
| **[Lathe](https://github.com/devenjarvis/lathe)** | 1.7k★. LLM-generated build-from-scratch tutorials worked through by hand | N/A | None |
| **[devatrophy.com](https://devatrophy.com)** | Scrimba lead-gen quiz → course funnel | Honor system | Self-reported 7,000+ takers, 53% lowest tier — unverified |

**Pricing:** Chestnut £0 / £15 / £40 per month. Two founders, no disclosed funding, no customers or testimonials published. Launched 20 Apr 2026; its Show HN scored 7 points. Early product with unverified traction, not an incumbent — but real, shipping, and charging money.

**What this changes.** Grit is not entering an empty space. It is entering a space with one funded-looking commercial entrant, one well-engineered open-source tool, and one funnel. The "nobody has built this" argument is retired.

**What it does not change,** and where the opening remains:

1. **Nobody closes the loop.** `atrophy` measures without teaching; Chestnut teaches without measuring. Neither can demonstrate it worked.
2. **Every core metric is self-reported.** `atrophy`'s headline number depends on the user not opening Claude — and it detects ten assistants and declines to use that detection.
3. **Nobody publishes outcome data.** All four borrow credibility from METR, PNAS, and Anthropic. None has longitudinal evidence.
4. **Team-level enforcement is unoccupied.** Individual introspection tools exist; the *enforced, non-punitive, employer-legible* signal does not.

---

## 7. Verification notes

- **Preprints:** Shen & Tamkin (arXiv:2601.20245), METR (arXiv:2507.09089), and Caosun & Aral (arXiv:2604.03501) are preprints. Treat effect sizes as provisional.
- **Population mismatch — the most important caveat in this document.** The mechanism evidence (Kazemitabaar, novices) and the skill-formation evidence (Shen & Tamkin, 52 novices via crowd-work) are both drawn from **learners, not working developers on their own repos**. The only study in Grit's actual target population is METR — 16 experienced OSS developers — and it measured *speed*, not skill. Every claim about skill retention in experienced developers is an extrapolation. Do not present it otherwise.
- **Corrected since first draft:** (a) Shen & Tamkin participants are *novice developers*, not professionals; (b) their six interaction clusters have n = 2, 3, 7, 4 and are not a validated finding; (c) "Iris" was a first author's name (Groher), not a tool; (d) CodeHelp's "95%" is 95% of 45 respondents on an extra-credit survey about interest in future courses; (e) Kapoor et al. was originally cited *in support of* optional guardrails — it is evidence against them.
- **Unverified products:** "QuestMind" and "Daily Quests" as distinct AI quest apps could not be confirmed and should not be cited as real.
- **Paying, not yet read:** the [Bastani correction](https://www.pnas.org/doi/10.1073/pnas.2518204122) exists (PNAS 403s on automated fetch). Verify before citing exact figures.
- **Fast-moving field:** Claude learning mode and ChatGPT Study Mode launched 2025–2026 and change between releases. Descriptions reflect the cited pages, not a live test.
- **Codefetch limits:** Exercism and Scrimba homepages returned 403 / JS-only bodies; pnas.org and mdpi.com also blocked automated fetch and were verified via search snippets and secondary full text.

### How these errors happened

The landscape survey was delegated to a research sub-agent tasked with finding *products*, not verifying *papers*. It compiled citations from search snippets without reading populations or findings, and the "52 professional programmers" framing was then written into the design docs by hand without checking the abstract. Kapoor et al. was cited from its title — "optional guardrails" — without reading that the study measures their failure.

The lesson for this repository: **a citation is not verified until its abstract has been read.** Titles and snippets are not evidence.
