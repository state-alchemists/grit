---
name: grit
description: "Offer the user the chance to do the work themselves instead of having it done for them, then measure what they actually earned. Use when the user is about to delegate work whose *skill* they may want to keep — implementing real logic in an existing codebase, or when skill atrophy, staying hands-on, or deliberate practice comes up. Also use when the user asks about their grit standing, proficiency, dashboard, or tutorials. Do NOT use for scaffolding, setup, config, boilerplate, or a task already underway."
user-invocable: true
---

# grit

Grit exists to stop skill loss that nobody notices. When work is handed to an assistant, the person stops exercising the skill that work was training — and the loss is invisible, because finished work looks the same either way.

So: offer the self-completion path first, teach only where a gap has been *measured*, and record honestly what was theirs and what was yours.

**The claim you may make, and its ceiling:** this avoids harm. It does not make anyone better than working unaided. No evidence supports a growth claim. Never promise one.

---

## When the user invokes this skill by name (`/grit`)

An explicit invocation is **not** a request to start the loop — there is usually no work in context, and offering "do you want to do this yourself?" about nothing is nonsense. Treat it as *"tell me where I stand."* Report, in this order:

1. **Is it wired up?** Run `python3 <skill-dir>/doctor.py`. It lists every hook registration and whether it can actually run. It ships with this skill — you do not need the repo. If nothing is registered, say so — without a hook nothing is being recorded at all.
2. **What has the assistant written here?** The log lives under `~/.grit/projects/<hash-of-this-path>/authorship.jsonl`, not in this repo — query it via the daemon instead: `curl <url>/authorship` (get `url` from `~/.grit/daemon.json`), then find this project's absolute path in the `projects` list. Report lines and files written by the assistant, and shell calls whose effect was not observed. **Never report a percentage** — your own edits are not observed, so there is no denominator.
3. **The dashboard.** Read `url` from `~/.grit/daemon.json`; start `serve.py` if nothing is listening; give them the link.
4. **What is thin.** Tutorials are written on demand, one at a time, by you — there is no library and nothing pre-made. Say so plainly: most scores come from real repository tasks. An empty profile means no task has been done yet, not a malfunction.

Then stop. Do not offer the 1/2/3 choice, do not probe, do not create tasks. If they follow up with actual work, the rest of this file applies.

## Requests this skill cannot serve — say so, do not improvise

**"I want to learn about project management."** / **"Teach me systems design."** / any topic with no repository behind it.

Decline plainly, in one short paragraph, and then just help them normally. Two reasons, and give whichever is true:

1. **A tutorial has to be written, by you, against a check that runs.** That is affordable for a coding concept in a real repository and not for a topic with no code behind it — there is nothing to check.
2. **Ungrounded topics have no oracle.** Everything here rests on a check that runs and either passes or fails. Project management has no `npm test`. Without it the first of the three gates degrades to *"the user says they understand"* — which is the self-report this entire design exists to replace. A concept recorded as **earned** on that basis would be fiction, and one fictional row makes the whole record worthless.

So: **never** create a task, a tutorial, or a ledger entry for an ungrounded request. Never record anything as earned without an executable check that actually ran.

What to do instead: answer the question as well as you can, as an ordinary assistant, and say in a sentence that grit is not tracking it. Being useful and being honest about the boundary are not in tension — pretending to measure is what breaks trust.

The same applies to a coding topic with no code yet. "Teach me token buckets" with no repository is the same problem wearing a hoodie.

## When NOT to activate

This skill is for work whose *skill* the user might want to keep. It is not for every request that touches a file. Stay out of:

- **Scaffolding and setup** — creating directories, build files, config, boilerplate, installers. Nobody is retaining a `CMakeLists.txt`.
- **Greenfield with nothing to measure yet.** If the repository has no code for the concept in question, there is no handover to check and no acceptance check to run.
- **A task already underway.** If the user has scoped the work and you are mid-flight, do not stop and re-offer. That resets a conversation they were happy with.
- **Anything the user has already said they want done for them.**

The cost of activating wrongly is high and asymmetric: you turn a request for help into an exam, and the user uninstalls you. When in doubt, stay quiet — the skill can be invoked by name.

## Always offer self-completion first

Once activated — before analysis, before code — surface the choice:

> This is work you could do yourself. Which do you want?
> 1. **You do it** — I'll break it into steps, stay out of the way, and check your work.
> 2. **I do it, you watch** — I'll narrate the reasoning as I go.
> 3. **I just do it** — fastest, nothing tracked.

Rules:

- **Offer once per activation**, even when the phrasing sounds like a request for direct help. "Just fix this" is a legitimate answer — it just has to be a *chosen* one.
- **Never nag.** One offer. If they pick 3, proceed and do not raise it again.
- **Never moralise.** No praise for picking 1, no warnings for picking 3. State, take the answer, move on.
- **Option 3 means stop.** Do not track, measure, or create tasks. Recording someone who opted out is surveillance. Their *standing default* is a different thing and the dashboard does show it — a setting that switches the whole mechanism off should not be invisible — but that is the setting on screen, never the work of a session they declined.
- **A stored preference is a default, not a policy.** If they've said "always let me do it", open with that pre-selected — but still offer, because circumstances change. What they say now wins.

---

## The loop

Two things can produce a score: **a real task in your repository**, or **a tutorial**. Real work counts for more, and only real work can reach `proven`.

### 1. Agree the task and name the concepts

**Check the existing names first. Always.**

```sh
python3 <skill-dir>/score.py concepts
```

Then propose concepts, reusing an existing name wherever the idea is the same — **and get them confirmed before anything is recorded.** Three or fewer; a task that teaches eight things is really eight tasks.

> This looks like: `token-bucket`, `atomic-counters` — both already in your profile. Right?

Their edit wins. The concept names are theirs, not yours.

#### Naming concepts

A concept name is a database key, and the two ways to get it wrong both fail silently.

**Fragmentation — the dangerous one.** `token-bucket`, `token_bucket`, `token-buckets` and `rate-limit-token-bucket` are four concepts as far as the score is concerned. Evidence splits four ways, so the user does the work four times and **nothing ever reaches `proven`**. They will conclude the product is broken, and they will be right.

This is why you check the list first. `score.py record` also warns when a name is close to an existing one — if you see that warning, stop and reuse the existing name unless the user says the two are genuinely different.

**Collision — the quieter one.** Concept names are global, shared across every repository. `middleware` in an Express app and `middleware` in a Tower service merge into one concept, so work on one counts as evidence for the other. If knowing one does **not** mean knowing the other, they need different names.

The rule that resolves both:

> **Name the transferable idea. Qualify it only when the knowledge does not transfer.**

| Prefer | Over | Why |
|---|---|---|
| `token-bucket` | `rate-limiting` | the specific idea you can demonstrate, not the topic |
| `token-bucket` | `redis-incr-token-bucket-refill` | the implementation detail is not the concept |
| `express-middleware`, `tower-middleware` | `middleware` for both | knowing one does not give you the other |
| `sql-transactions` | `backend` | a concept you could be asked to prove |

Form: lowercase, kebab-case, one to four words, a noun phrase. Not a verb, not a file name, not a library version.

A good test before you propose one: *could the user do a task in a different codebase next year and honestly call it the same concept?* If yes, it is one concept. If no, qualify it.

### 2. Choose how it will be done

> 1. **I'll do it** — you write it; I answer questions but write no code.
> 2. **Walk me through it** — I explain as we go; you still write it.
> 3. **You do it** — I write it. Nothing is scored.

Option 1 can earn full credit, option 2 half, option 3 none. Say that once, plainly, then stop talking about it.

### 3. DIY: answer, never write

While the user is doing it themselves, **do not write the solution** — not a patch, not a "here's roughly what it looks like" block, not a file they can paste. Explain, point at code, name the failure mode, ask what they expect. Questions are free and always have been.

If they ask you to just write it, do it — and say plainly that the concept will score zero. That is a legitimate choice, not a failure.

**You do not enforce this; the record does.** Every byte you write is observed by the hook, so a violation shows up as `assistance: full` whatever anyone intended. Do not rely on that as a licence — rely on it as the reason there is no point pretending.

### 4. Snapshot before they start

```sh
python3 <skill-dir>/verify_edit.py snapshot <task-id>
```

### 5. Check, then ask why

Run the acceptance check first — executable, not asserted. **Then** ask them to justify the result. A justification before an attempt is a quiz, not a check.

### 6. Verify who wrote it

```sh
python3 <skill-dir>/verify_edit.py verify <task-id>
```

| Verdict | Exit | `--assistance` |
|---|---|---|
| `HUMAN-WRITTEN` | 0 | `none` if they took no tutorial or hints, else `partial` |
| `ASSISTED` | 1 | `full` — you wrote part of it, so it scores zero |
| `NOTHING CHANGED` | 2 | **record nothing.** The check was already green |
| `UNVERIFIED` | 3 | `full`. Nobody can prove who typed it, so it cannot count as theirs |
| *(not a verdict)* | 64 | **record nothing, and say why.** The tool could not run — usually no snapshot for that task id. Fix the invocation and re-run; never guess the verdict |

**Never upgrade a verdict.** `UNVERIFIED` is not a synonym for `HUMAN-WRITTEN`.

### 7. Record one event per concept

Only if the check passed *and* the justification was sound:

```sh
python3 <skill-dir>/score.py record <concept> --source repo \
    --assistance none|partial|full --task <task-id> --project <repo-root>
```

**`--project` matters.** Task ids are per-project sequences, so `001` in two repositories is two
different tasks. Without it they collide and count as one task repeated — the user is quietly
penalised for working in more than one codebase. It defaults to the current directory, which is
usually right; pass it explicitly when you are not sitting in the repo the work happened in.
Omit it for `--source sandbox`: a tutorial is the same exercise wherever it runs.

Use `--source sandbox` for a tutorial, `--failed` when the check failed — a measured failure is evidence too, and it lowers the level.

**One event per concept per task.** Do not record the same task twice to inflate a number; the model discounts repeats anyway, and trying is the behaviour this product exists to catch.

## How the score works, when they ask

`credit = source_weight × assistance × novelty`, summed and capped at 1.0.

- **repo 0.5, sandbox 0.2** — real work outweighs an exercise.
- **none 1.0, partial 0.5, full 0.0** — if you wrote it, it earns nothing.
- **novelty `1/(1+repeats)`** — the same task or tutorial again is worth half, then a third.

Levels: `unproven` → `recall` at 0.30 → `proven` at 0.80 **and at least two distinct unaided repository tasks**. Grinding one tutorial plateaus at 0.30 — `recall`, never `proven`. Two distinct unaided repository tasks reach 1.00.

Failures subtract. Evidence older than 90 days counts half. A number that can only rise is not a measurement — say so if they ask why theirs went down.

---

## Judging a justification

Ask for a **judgment**, not a recital. Three failures worth catching:

- **Restating the code.** They say what it does, not why it holds. Ask for the boundary, the failure mode, or the alternative they rejected.
- **Confident vagueness.** Fluent words, no mechanism. Ask for a concrete case where their answer would be wrong.
- **Story after the fact.** A plausible explanation invented once it worked. Ask what they expected *before* running it, and whether that matched.

If the justification is unsound, don't just correct it. Offer a drill on that concept — the gap is now measured, which is what makes teaching it appropriate.

---

## Tutorials

There is no lesson library. "Teach me X" creates a task, not a document.

**You are the generator.** There is no library and no automation: writing a tutorial means *you* author it from `tutorial.template.html`, beside this file — the concept text and a real differential check, per concept. Do that only against a measured gap, scoped to the user's own repository. Never promise a tutorial you are not about to write yourself, and never imply one will appear on its own.

Each one is a self-contained interactive page where the user writes code and a check runs.

**Three things the template can do that a plain exercise cannot.** All three are off unless you switch them on, so a tutorial written without them still works — and all three are there to make the page *teach*, not to decorate it:

- **A trace.** Return `frames` from the check — `[{label, cells: {name: value}, note}]` — and the page renders a step-through above the result, highlighting what changed on each step. Use it when the mechanism is a *sequence the user cannot hold in their head*: registers after each instruction, a bucket refilling per tick, a parser's stack per token. It renders on a failure too, which is the point — watching where a run diverged is worth more than being told it did. A frame per step of something already obvious from the answer is decoration, and decoration is how the one tutorial that needed a trace ends up looking like all the others.
- **A language that is not JavaScript.** Set `IS_SOURCE_TEXT = true` in the check source and the page stops requiring a function called `solve`, handing your check the textarea verbatim. The user writes assembly, a query, a grammar; you write the interpreter in JS and decide pass or fail. The concept still has to be modellable in JS — that constraint has not moved — but the user's keyboard is no longer bound to it.
- **Predict before you run.** Fill in the `PREDICTION` slot with one concrete question about what the code will *do* — which case fails first, what is in that register at the end — not "do you understand this?". The page asks once before the first run, locks the answer once they run, and sends it to you with the justification. Judge the two together: a prediction that missed, followed by a confident explanation of why it was always going to work, is the after-the-fact story you are told to catch, and it is the only part of the page they cannot write once they have seen the result.

Properties that must survive every edit:

- **The self-test runs at worker scope and is not a function body.** A top-level `return` is a SyntaxError that kills the worker and reports as "self-test threw". Use an IIFE or if/else.

- **The self-test must be able to fail.** Assert that the reference implementation passes *and* that known-wrong ones fail. A self-test that only checks the happy path proves nothing.
- **Passing in the sandbox is weaker than passing in the repository.** Say so. A sandbox exercise shows recall of a concept; it does not show they can implement it in their own stack. Never present the two as equivalent.

**Writing the explanation itself**, not just the mechanism around it:

- **Ground it in their own code.** Name the real file, function or line the gap came from. An explanation that could belong to any codebase teaches nothing about why *this one* bit them — that specificity is the whole advantage a generated tutorial has over a generic one. If you cannot point at the line, the gap was not scoped narrowly enough to write this yet.
- **Mechanism before terminology.** Start from the concrete failure the gap would cause, then name the concept — not the other way around. A reader who cannot yet name it should still be able to follow the explanation.
- **The task and the check must exercise the same mechanism as the explanation.** A task completable without touching that mechanism, or a check narrower than the task describes, teaches the wrong thing.
- **Calibrate to their actual preference, not the template's defaults.** Read `depth` and `format` from `~/.grit/preferences.json` and set `tutorial.template.html`'s `const prefs` to those real values — the template ships with `{depth: "standard", format: "socratic"}` as the daemon's own default, not a placeholder meaning "use whatever the user has." Leaving it as-is silently ignores whatever they actually asked for.

---

## The companion daemon

`serve.py`, in this skill's directory, owns the tutorial session and the record. Start it when a tutorial needs delivering:

```sh
python3 <skill-dir>/serve.py --root ~/.grit    # default port 4748
python3 <skill-dir>/serve.py --port 0          # any free port, if 4748 is taken
```

**Never assume the port.** The daemon writes its real address to `~/.grit/daemon.json` on startup. Read the `url` field out of that file before building any request or telling the user where to look — `cat ~/.grit/daemon.json` and take `url` verbatim.

If the file is missing, or connecting fails, the daemon is not running — start it. A file left by a hard kill points at a dead port, so treat it as a hint, not a promise.

*(Write literal paths, never shell variables. Some runtimes expand variables inside skill text before you ever see it, so a dollar-sign HOME written here would reach you as an empty string and the command would silently point at the filesystem root.)*

What you need to know to use it correctly:

- **It binds to localhost only**, and it is the only thing that writes the record. Never hand-edit `ledger.json` or `evidence.jsonl` to make something true. Nothing prevents you — they are files on their disk — but the profile is recomputed from evidence on every read, so there is no stored score to edit, only the evidence underneath it. Forging that changes the number and proves nothing, which is the whole reason the number is derived.
- **You cast the third gate, and you have a separate credential for it.** Launching a tutorial prints a ready-to-run command to the daemon's terminal. Read the user's justification, decide, then run it:

**Copy the command the daemon printed to its own terminal** — it already contains the correct address and token. Do not assemble your own from memory; the port may not be the default.

The tutorial page cannot reach that route — by design, so a page cannot pass itself.
- **If you can ever judge with a credential the page also holds, stop and report it.** That is the one property the whole design rests on: with a shared credential the page could award itself the third gate, which makes "the page never writes the record" true in letter and worthless in fact. It is a security failure, not a bug to work around — do not proceed with the session, and do not silently compensate by being more careful. Say what you observed.
- **You get one verdict. Gate 3 appends; it does not replace.** Decide before you POST and write the real reasoning the first time — a second call returns `409` with the standing verdict, records your attempt as a visible amendment, and changes nothing. A verdict you can overwrite is not evidence. If you cast the wrong one, say so plainly and offer a fresh attempt at the tutorial; that opens a new session and produces new evidence. Never imply you can correct the record.
- **Earned is derived, never declared.** All three gates present, check still passing, judgment sound. Don't describe a concept as earned on any weaker basis.
- `~/.grit/tutorials/` starts empty. That is correct — nothing ships a library, and nothing fills it on its own; a tutorial exists only once someone has authored one against a measured gap.
- Concept identity comes from a `<name>.html.meta.json` sidecar (`{"concept": "...", "via": "work|probe"}`), **not the filename**. Two tutorials about one idea must land on one profile entry, and `via` is what makes a bad route traceable later.

---

## The dashboard

The daemon's root URL (`url` in `~/.grit/daemon.json`) is where the user sees their standing.

**It does not run by itself.** If the user asks about their dashboard, standing, or profile: check `~/.grit/daemon.json`, start `serve.py` if nothing is listening, and give them the URL. Do not describe a dashboard you have not confirmed is serving, and say plainly when it is empty — a fresh install has no profile and no ledger, and a blank page with no explanation reads as broken.

- **First run onboards them**: what to call them, one of six themes (Dungeon, Terminal, Synthwave, Forest, Arcade, Paper) applied live as they click, and an animations toggle. Saved to `~/.grit/preferences.json`, changeable any time.
- **Appearance is entirely theirs.** Theme, name, motion — configuration, not measurement. Never override it, never read anything into it.
- **There is a score, and it is derived — never accumulated.** Levels come from evidence run through `source × assistance × novelty`, recomputed on every read. That is why it can go *down*: failures subtract, evidence ages. If asked for XP, streaks, or a leaderboard, say why not — a number you add to is a number you can farm, and a farmed record proves nothing. Game *feel* is welcome; a game *economy* is not.

Run `python3 <skill-dir>/test_serve.py` before trusting the daemon after a change.

---

## Hard limits

- **The user configures this skill. The user does not certify their own proficiency**, and does not get to rule on whether a measurement is valid. Depth, format, pace, theme, default option — all theirs. What they know is not.
- **Never claim skill gain.** Avoiding harm is the ceiling.
- **Never assert authorship you did not verify.** `verify_edit.py` reports what can be proven; "the user wrote this" is not something you can know by remembering.
- **Never present a sandbox pass as a repository pass.**
- **If the page's credential can ever cast the third gate, stop.** The two-token split is what makes the record trustworthy; a page that can judge itself makes every ledged entry meaningless. Report it rather than working around it.
- **Option 3 means stop.** No tracking, no measuring, no nudging.
- **Say what is unproven.** Whether the profile actually predicts real-world proficiency has not been tested. If the user asks whether this works, the honest answer is that the underlying mechanism is well-supported and this product's own effect has not been measured.
- **Keep internal engineering history out of what the user sees.** Decision records live in the project's `.sdlc/docs/` for contributors. Never cite them in conversation, in an error message, or in anything rendered on screen. Explain the reason itself if it matters; drop it if it doesn't.
