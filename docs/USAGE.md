# Usage — A Campaign From Start to Finish

A worked example showing what using Grit actually looks like. The scenario: adding rate limiting to an existing Node API.

This is a design walkthrough, not a transcript of a working tool. Interaction shapes are representative of the intended experience.

---

## A note on this walkthrough's design

This example reflects the design as first written: per-mission modes with a free-attempt default. [DESIGN.md §7](DESIGN.md) now argues that the "Attempt" mode shown below should be replaced with **step-gated dialog** — the user states what the code must do at each stage before it is revealed ([Kazemitabaar et al., IUI 2025](https://arxiv.org/abs/2410.08922)). The reason: Kapoor et al. (2025, N=885) measured this style of voluntary guardrail failing, with 50% of students taking the bypass. Step-gating has no bypass button.

The example below is kept as-is because it shows the tracking model, the tutorial generation, and the honest ledger — all of which survive the change. Read the mode mechanics as provisional.

---

## 1. Starting a campaign

You invoke the skill on a problem:

> **You:** Let's add rate limiting to our public API.

Grit interviews you before writing anything. It needs to know the goal precisely enough to write an acceptance check, and it needs to know what you already know — that determines mission sizing and default modes.

> **Grit:** A few questions before I draft the plan.
>
> 1. What does "done" mean concretely — is there a specific endpoint or traffic pattern?
> 2. Do you have existing middleware, or is this greenfield?
> 3. How familiar are you with token bucket / sliding window algorithms?
> 4. Any constraint on dependencies, or is a library acceptable?

You answer. Grit drafts a campaign.

---

## 2. Reviewing and validating the plan

> **Grit:** Here's the plan. 7 missions, ordered by dependency.
>
> | # | Mission | Teaches | Check |
> |---|---------|---------|-------|
> | 001 | Understand the existing middleware chain | middleware ordering | `npm test -- middleware` |
> | 002 | Define the rate limit policy | policy design, config | `npm test -- config` |
> | 003 | Implement the token bucket | token bucket, atomic counters | `npm test -- rate-limiter` |
> | 004 | Wire it into the middleware chain | middleware composition | integration test |
> | 005 | Add the 429 response shape | API contracts | `openapi.yaml` has 429 |
> | 006 | Handle distributed state | Redis, race conditions | concurrent test |
> | 007 | Document and ship | — | docs build |
>
> Definition of done: 429 responses under load, integration test passes, docs updated.
>
> You said you know sliding window but not token bucket — so 003 defaults to Walkthrough, everything else defaults to Attempt. Approve, or change anything?

You push back: mission 006 depends on infrastructure you don't have yet. Grit splits it and reorders. **Nothing is written until you accept.**

On acceptance, Grit validates structurally:

- every mission has a checkable acceptance criterion ✓
- dependencies are acyclic ✓
- the mission set reaches the definition of done ✓

Then it writes `.grit/campaign.json`. *(Validation catches the class of plan that reads well and doesn't add up — the missing step, the circular dependency, the criterion nobody can check.)*

---

## 3. Starting a session

You open the repo and ask Grit where you are.

> **Grit:** Campaign: rate-limiter — 0/7 missions complete.
>
> **Next: Mission 001 — Understand the existing middleware chain** Teaches: middleware ordering, request lifecycle Check: `npm test -- middleware` → exit 0 Depends on: nothing
>
> ``` [1] Walkthrough — teach me first [2] Attempt     — let me try            (default) [3] Solve       — just do it ```
>
> Note: this mission is mostly reading. Attempt means you read the code yourself and I answer questions. That's usually the right call for orientation work.

You pick **Attempt**.

---

## 4. Working in Attempt mode

You read the middleware chain. You get stuck on how ordering interacts with error handling and ask about it.

> **You:** Why does the error handler have to be registered last?
>
> **Grit:** [Explains Express's middleware registration order and why error handlers — the 4-arity functions — must come after routes. Points at your `app.ts:47`.]
>
> Asking questions doesn't change the mission's status. Only me writing the solution does.

You figure it out, run the check yourself:

```
$ npm test -- middleware
✓ 12 passing
```

> **Grit:** ✓ Mission 001 complete — **earned** (attempt, no assistance). Ledger: 1 earned / 0 assisted / 7 total. Next: Mission 002 — Define the rate limit policy.

---

## 5. Hitting a wall — and switching modes

You reach mission 003, the token bucket, which you said you don't know. You try Attempt anyway.

Twenty minutes in, you're guessing at refill timing.

> **You:** I don't know how to make the refill atomic.
>
> **Grit:** That's the core of it. Two options:
>
> ``` [1] Walkthrough — I'll generate the tutorial on token bucket + atomic counters [2] Solve       — I'll implement it, you review the diff ```
>
> Staying in Attempt and guessing is also available, but I'd not recommend it for a concept you haven't met.

You pick **Walkthrough**.

> **Grit:** *[Generates `.grit/tutorials/003-implement-token-bucket.md`, scoped to your repo: the token bucket model, why naive read-modify-write loses updates, how your Redis client exposes atomic operations, and where the counter belongs in your existing structure. Shows adjacent patterns and examples. Does not write the implementation.]*
>
> The tutorial is at `.grit/tutorials/003-implement-token-bucket.md`. Work through it and ask when you're stuck.

The mission's `mode_history` now records `[attempt, walkthrough]` and it is marked `assisted: true`. The ledger will show it as assisted, because it was.

---

## 6. Cheating, visibly

Mission 005 is the 429 response shape — boilerplate you've written a dozen times and will never learn anything from.

> **You:** Just do this one. I've done it before.
>
> **Grit:** Fine — switching mission 005 to Solve. I'll implement it and you review the diff. It'll be recorded as **assisted (solved by AI)**, so the ledger will show it. That's the deal — no objection, just a mark.
>
> *[Implements the response shape, shows the diff.]*
>
> Review: [summary of what changed and where].

This is the design working as intended. Paternalistically blocking this would just push you to a plain assistant window, where nothing is tracked at all.

---

## 7. Mid-campaign check

> **Grit:** Campaign: rate-limiter — 5/7 complete.
>
> | Status | Count | Missions |
> |--------|-------|----------|
> | Earned | 3 | 001, 002, 004 |
> | Assisted | 1 | 003 (attempt → walkthrough) |
> | Solved by AI | 1 | 005 |
> | Remaining | 2 | 006, 007 |
>
> Concepts you've now worked with directly: middleware ordering, policy design, middleware composition. Concepts you received rather than built: token bucket internals, 429 response shape.

The report names what you got for free. That's the point of the whole exercise — a plain assistant cannot tell you this, because it isn't tracking it.

---

## 8. Closing the campaign

All seven missions pass and the definition of done is verified.

> **Grit:** Campaign **rate-limiter** complete.
>
> - 7/7 missions — 5 earned, 1 assisted, 1 solved by AI
> - Verified: 429 under load ✓, integration test ✓, docs ✓
> - You built: the limiter, the policy layer, the middleware wiring, distributed state handling
> - The AI built for you: the 429 response shape
>
> If you want the response-shape pattern to count, redo 005 in Attempt mode — I'll reopen it as a new mission.

Reopening as a *new* mission rather than editing the old one keeps the ledger honest: the original stays in history as solved-by-AI, and the redo is a separate earned record.

---

## Where things live after this

```
your-repo/
└── .grit/
    ├── campaign.json                            # the agreed plan
    ├── ledger.json                              # earned vs assisted, with history
    ├── missions/
    │   ├── 001-understand-existing-middleware.json
    │   ├── 002-define-rate-limit-policy.json
    │   └── ...
    └── tutorials/
        └── 003-implement-token-bucket.md        # generated on demand, cached
```

Committing `.grit/` is the intended workflow — the plan and the record belong with the code they describe.

---

## Modes at a glance

| Mode | You do | AI does | Ledger |
|------|--------|---------|--------|
| **Walkthrough** | Works through tutorial | Teaches, hints, points at concepts | `assisted` |
| **Attempt** | All of it | Answers questions only | `earned` |
| **Solve** | Reviews the diff | Implements it | `assisted` (solved by AI) |

Asking questions in Attempt mode is free — it never flips the mission, or the mode would be pointless. Only the AI writing the solution does.
