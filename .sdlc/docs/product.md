# Grit — Product Overview

How to install and use it is in [README.md](../../README.md); the full argument for the scope, and what is unproven, is in [DESIGN.md](DESIGN.md).

## Problem Statement
AI assistants optimize for throughput. The path of least resistance is to let the assistant write everything, which feels productive and quietly erodes the skill the work used to exercise. The loss is invisible to the person experiencing it: finished work looks the same either way, and METR's experienced developers were 19% slower with AI while believing they were 20% faster.

Grit offers, when the assistant is about to write code, to let the user do the work themselves; then measures who actually wrote the result, from git and a hook log, and turns unaided work into a per-concept level the user did not award themselves. The supportable claim is harm avoidance: no study shows a tool making anyone better than working unaided.

## Target Users
| User Role | Primary Goal |
|-----------|-------------|
| Developer delegating work to an AI coding assistant | Keep a skill they still want, and see — measured, not self-reported — whether they are exercising it |
| Beginner learning a subject with no repository yet | Do real tasks in a practice repository with a failing test, scored like any other work |
| Contributor to this repository | Change the mechanism without breaking the record's integrity; the conventions are in [AGENTS.md](../../AGENTS.md) |

## Success Criteria
- **Functional**: a task done unaided through the skill ends in a verdict from git plus the hook log and scores; a task the assistant wrote any part of scores nothing, whatever anyone intended.
- **Non-Functional**: a hook can never block a tool call; Python standard library only, with no build step; every measurement stays on the machine, served on loopback only.
- **Business**: none is claimed yet. The outcome that would justify the product — a `shipped` level predicting unassisted performance — is specified in [ADR 0012](adr/ADR-0012-profile-validity-is-the-critical-path.md) and unrun.

## Scope
### In Scope
- Graded scoring from real repository work, per concept and per person.
- Authorship measurement: the hook, `verify_edit.py`, per-task verdicts.
- The offer and the DIY handover: solo, guided or hand-off, with guidance pre-selected only on a recorded failure.
- The local daemon and dashboard.
### Out of Scope
*Each item states the trade that makes it a non-goal, so it is not mistaken for a missing feature.*
- **Team or hosted features** — local and never transmitted is the entire privacy claim; a server would end it.
- **Cross-user benchmarking** — concept names are chosen per conversation, so two people's records are not comparable.
- **Tutorials or lessons** — built, never produced evidence, removed: repository tasks are the only source.
- **Anything without an executable oracle** — without a check that passes or fails, scoring degrades to the self-report the design replaces.
- **Any claim beyond harm avoidance** — no study shows a tool producing skill gains over working unaided.
- **The onboarding battery and per-concept probe** — deferred, not rejected: real tasks populate the profile without them, and [ADR 0011](adr/ADR-0011-routing-on-a-measured-profile-deferred.md) governs how routing must work if they are built.

## Alternatives & Positioning
*Surveyed 2026-09. Every row carries a source below. Products are described from their own pages and documentation, not a live test, unless a row says otherwise.*

| Alternative | What it does | Where it is ahead of Grit | What Grit does differently |
|-------------|--------------|---------------------------|----------------------------|
| Status quo — the assistant's default mode | Writes everything it is asked to | Zero friction; fastest for the task at hand | Nothing records who did the work, and the loss is not self-detectable — METR's developers were 19% slower and believed they were 20% faster |
| Chestnut | MCP hook into the coding agent infers gaps from shipped code, generates micro-courses, keeps a skillset model. £0 / £15 / £40 per month; launched 20 Apr 2026 | Teaches: generates courses from your own work; a shipping, paid product | Measures who did the work, not only what to learn next. Chestnut enforces nothing and publishes no outcome data |
| `atrophy` CLI | MIT. Spaced drills with AI off, auto-graded, Elo per skill, charts an unaided-vs-assisted "dependence gap" | Spaced repetition over time — a retention signal Grit does not have | Authorship comes from a hook on real repository work, not an honor system; `atrophy` detects ten assistants, warns, and never blocks |
| Lathe | 1.7k★. LLM-generated build-from-scratch tutorials, worked through by hand | Structured teaching | Scores only repository work; tutorials were removed as an evidence source |
| devatrophy.com | Scrimba lead-generation quiz feeding a course funnel | Reach — self-reported 7,000+ takers, 53% in the lowest tier (unverified) | Measures work, not a quiz |
| Claude Code `/output-style learning` | Pauses and leaves `#TODO` sections for the human; `explanatory` explains trade-offs; Claude.ai has a Socratic "Learning" preset | Built in, no install; the do-it-yourself / let-it-do-it axis already exists at the assistant level | Records what the human did; the output style keeps no record |
| ChatGPT Study Mode | Free Socratic tutoring: guiding questions, hints, knowledge checks. Reported to give the answer if pushed | Free, general-purpose, polished | Works inside your repository, not a chat |
| Boot.dev | Lesson → challenge curriculum with XP and an AI tutor, **Boots**, that gives questions and hints instead of answers | The best real precedent for the pedagogy; a full curriculum | Your repository's work, not a fixed curriculum |
| CodeHelp, CodeAid, Groher et al., PeteChat | Guardrailed classroom LLM assistants that withhold complete solutions (CodeHelp: 52 students, 12 weeks) | Deployed and studied in courses; the design precedent Grit's guidance owes its shape to | Aimed at working developers on their own repositories. None of these supplies outcome data — they are design precedent, not evidence |
| HagiCode | Agentic workspace wrapping 13 agent CLIs, with an OpenSpec plan workflow; gamifies the *agents* (Heroes, Dungeons, XP, Battle Reports) | Plan → validate workflow; multi-agent workspace | Measures the human, not the agent |

**Adjacent, not competing.** Gamified task managers — Task Quest (Epics → Quests → Tasks with an AI Quest Planner, generic tasks, no code), MainQuest (RPG habit app), MagicTask (team tasks with XP). Agent gamification — vantage-quest (a Go data layer for quest tracking in agentic workflows, v0.1.0), Agent Quest (a 2D village visualising running sessions), `gh dungeons` (a repo turned roguelike). Gamified learning — Codédex, Exercism, Codewars, CodinGame, Scrimba, Codecademy, Treehouse, SoloLearn: none attach to *your* repository's work. Progression models — the NSA's skills-service adds skill trees to existing training apps; Project SkillTree is an unrelated self-improvement app.

**The space is occupied.** An earlier survey claimed no product did this; it had missed Chestnut, `atrophy`, Lathe and devatrophy.com. Grit is entering a space with one commercial entrant, one well-engineered open-source tool and one funnel. What remains open:

1. **Nobody closes the loop.** `atrophy` measures without teaching; Chestnut teaches without measuring. Neither can demonstrate it worked.
2. **Every core metric is self-reported.** `atrophy`'s headline number depends on the user not opening an assistant it can already detect.
3. **Nobody publishes outcome data.** All four borrow credibility from METR, PNAS and Anthropic; none has longitudinal evidence. Neither does Grit — see [DESIGN.md §4](DESIGN.md#4-what-is-still-unproven).
4. **Team-level enforcement is unoccupied.** Individual introspection tools exist; an enforced, non-punitive, employer-legible signal does not. Grit does not occupy it either: its measurement is local and never transmitted.

**The uncomfortable precedent.** The closest published match to Grit's *original* design — a per-task choice of tutorial, attempt or auto-solve — is Kapoor et al. (N=885), a study of that design failing: half the students took the "See Solution" bypass, the weakest most often. That design was abandoned ([ADR 0011](adr/ADR-0011-routing-on-a-measured-profile-deferred.md)), as was an accumulated, farmable progression score ([ADR 0009](adr/ADR-0009-graded-score-from-capped-evidence.md)). The research behind this is in [DESIGN.md §5](DESIGN.md#5-evidence).

**Positioning in one line:** who wrote the code is measured by a hook, not reported by the user — in a field where every alternative either teaches without measuring or measures on the honor system. That is a claim about the signal, not about skill gain; no study shows a tool making anyone better than working unaided.

**Verification notes.** HagiCode's gamification internals come from its own documentation and marketing. vantage-quest's GitHub page 404s; the module is published on pkg.go.dev. Exercism and Scrimba homepages returned 403 / JS-only bodies and are described from search snippets. "QuestMind" and "Daily Quests" appear only in listicles and student papers and could not be confirmed as shipping products — do not cite them. Claude's learning mode and ChatGPT Study Mode change between releases; descriptions reflect the cited pages. This section ages fastest: re-date it when you revise it.

**Sources:** [Chestnut](https://chestnut.so) · [`atrophy`](https://github.com/ashutosh-rath02/atrophy) · [Lathe](https://github.com/devenjarvis/lathe) · [devatrophy.com](https://devatrophy.com) · [Claude learning style, ZDNet](https://www.zdnet.com/article/claude-can-teach-you-how-to-code-now-and-more-how-to-try-it/) · [Claude output styles, Tessl](https://tessl.io/blog/claude-code-now-lets-you-customize-its-communication-style) · [ChatGPT Study Mode](https://openai.com/index/chatgpt-study-mode/) · [Study Mode FAQ](https://help.openai.com/en/articles/11780217-chatgpt-study-mode-faq) · [Boot.dev](https://www.boot.dev/) · [CodeHelp](https://codehelp.app/) · [CodeHelp paper](https://dl.acm.org/doi/fullHtml/10.1145/3631802.3631830) · [CodeHelp PDF](https://arxiv.org/pdf/2308.06921) · [CodeAid](https://arxiv.org/html/2401.11314v2) · [CodeAid, CHI 2024](https://dl.acm.org/doi/10.1145/3613904.3642773) · [Groher et al.](https://arxiv.org/html/2604.11836) · [PeteChat](https://arxiv.org/html/2606.09845) · [HagiCode](https://hagicode.com/en-US/) · [HagiCode overview](https://docs.hagicode.com/en-US/product-overview/) · [HagiCode gamification](https://docs.hagicode.com/en-US/blog/2026-03-16-gamifying-ai-coding/) · [HagiCode on Steam](https://store.steampowered.com/app/4625540/Hagicode/) · [vantage-quest](https://pkg.go.dev/github.com/KOLLECTABLES/vantage-quest/quest) · [Agent Quest](https://github.com/FulAppiOS/Agent-Quest) · [`gh dungeons`](https://github.blog/ai-and-ml/github-copilot/dungeons-desktops-building-a-procedurally-generated-roguelike-with-github-copilot-cli/) · [Task Quest](https://www.sourcelogic.ai/) · [MainQuest](https://www.mainquest.net/) · [MagicTask](https://www.magictask.io/) · [Codédex](https://www.codedex.io/) · [Exercism](https://exercism.org/) · [Codewars](https://www.codewars.com/) · [CodinGame](https://www.codingame.com/) · [Scrimba](https://scrimba.com/) · [SkillTree](https://skilltreeplatform.dev/overview/) · [skills-service](https://github.com/NationalSecurityAgency/skills-service) · [Project SkillTree](https://www.projectskilltree.com/) · [Kapoor et al.](https://arxiv.org/abs/2504.11146) · [METR](https://arxiv.org/abs/2507.09089)

## Key Stakeholders
| Stakeholder | Interest |
|-------------|----------|
| Go Frendi | Author and decider of every recorded decision |
| Developers using the skill | A record of their own work they can trust, kept on their own machine |
