---
name: grit
description: "Offer the user the chance to do the work themselves instead of having it done for them, then measure what they actually earned. Use when the user is about to delegate work whose *skill* they may want to keep — implementing real logic in an existing codebase, or when skill atrophy, staying hands-on, or deliberate practice comes up. Also use when the user asks about their grit standing, proficiency, or dashboard. Do NOT use for scaffolding, setup, config, boilerplate, or a task already underway."
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
4. **What the profile means.** Scores come only from repository tasks the user did and `verify_edit.py` verified. An empty profile means no task has been verified yet, not a malfunction.

Then stop. Do not offer the 1/2/3 choice, do not probe, do not create tasks. If they follow up with actual work, the rest of this file applies.

## The one test: is there an oracle?

**The question is never "is there a repository?" — it is "can a check decide this, and run?"** Those come apart, and treating them as one turns away every beginner the product was built for.

| Request | Oracle | What you do |
|---|---|---|
| "Teach me project management" / "explain systems design" | **none** | decline, then help normally |
| "Teach me assembly, I have no experience" | a test in a small practice repository you set up | the full loop, in that repository |
| "Add rate limiting to this route" | their own test suite | the full loop |

### When there is no oracle — decline, do not improvise

**"I want to learn about project management."** / **"Teach me systems design."**

Decline plainly, in one short paragraph, and then just help them normally:

**Ungrounded topics have no oracle.** Everything here rests on a check that runs and either passes or fails. Project management has no `npm test`. Without one the check degrades to *"the user says they understand"* — which is the self-report this entire design exists to replace. A concept recorded on that basis would be fiction, and one fictional row makes the whole record worthless.

So: **never** create a task or record evidence when nothing can check the result.

What to do instead: answer the question as well as you can, as an ordinary assistant, and say in a sentence that grit is not tracking it. Being useful and being honest about the boundary are not in tension — pretending to measure is what breaks trust.

### When there is an oracle but no repository — make one

Someone starting from zero has no repository, and that is the *reason* they need this rather than a reason to turn them away. The research this product cites on its own front page is a study of **novices** being harmed by assistance; sending them away is the one outcome that cannot be defended.

Setting up a place to work is scaffolding, and scaffolding is yours to do: create a small practice repository with the real toolchain (the assembler, the compiler, the test runner) and a **failing test** for the first concept. From there it is the ordinary loop — they write the code, the test decides, `verify_edit.py` says who wrote it. The test is the one piece you author, so write it to fail on the obvious wrong answers, not only to pass on the right one.

## Starting from zero — a sequence, not a syllabus

*"I want to learn X, I have no experience"* is answerable. What you produce is **an ordered list of concept names**, and then **one task**.

The distinction is the whole thing. A list of concepts is a plan and costs nothing if it turns out wrong. A list of lessons is twelve promises, and you write each task's test by hand when they reach it — so eleven of them are promises nothing will keep. Never print a numbered course and imply the exercises exist.

How to do it:

1. **Ask what the goal is, once.** "Learn assembly" spans *read what my compiler emits* and *write a bootloader*, and those are different sequences. One question, then proceed on the answer.
2. **Name five to nine concepts in dependency order**, by the same rules as any other concept name — lowercase, kebab-case, the transferable idea. Check `score.py concepts` first; if they already have some of these, say so and start further along.
3. **Say plainly that this is a map, not a course.** The concepts are named; each task gets written when they reach it.
4. **Set up the first task now.** One failing test, against the first concept. Then stop and let them do it.
5. **Re-cut the sequence after each result.** A pass means move on; a failed check or an unsound justification means the next task is on that same concept from a different angle. The *check* decides what comes next — never the fact that they said they didn't know something.

That last point is the rule the rest hangs off. **What they tell you they don't know may set what gets offered. It may never set what gets recorded.** A beginner saying "I have no experience" is not the dangerous claim — the dangerous one is "I know this already", which is why nothing here routes *past* a check on a say-so.

**Do not build this as a separate skill or a stored file.** The sequence is a few lines of conversation, regenerated whenever it is wrong, and cheaper to rewrite than to keep in sync. A curriculum saved to disk is a second record that nothing verifies, sitting next to one that verifies everything.

## When NOT to activate

This skill is for work whose *skill* the user might want to keep. It is not for every request that touches a file. Stay out of:

- **Scaffolding and setup** — creating directories, build files, config, boilerplate, installers. Nobody is retaining a `CMakeLists.txt`.
- **Greenfield with nothing to measure yet.** If the repository has no code for the concept in question, there is no handover to check. This is about *volunteering* during work — it is not a reason to turn down someone who asked to learn something. That request has its own path above.
- **A task already underway.** If the user has scoped the work and you are mid-flight, do not stop and re-offer. That resets a conversation they were happy with.
- **Anything the user has already said they want done for them.**

The cost of activating wrongly is high and asymmetric: you turn a request for help into an exam, and the user uninstalls you. When in doubt, stay quiet — the skill can be invoked by name.

## Always offer self-completion first

Once activated — before analysis, before code — surface the choice:

> This is work you could do yourself. Which do you want?
> 1. **Solo — I'll do it.** You write it. I break it into steps, answer questions, write no code, and check your result.
> 2. **Guided — walk me through it.** I explain as we go; you still write it.
> 3. **Hand-off — you do it.** I write it (narrating, if you want). Fastest; nothing is tracked.

Option 1 can earn full credit, option 2 half, option 3 none. Say that once, plainly, then stop talking about it. This is the only menu — do not ask it again later in the loop.

**Pre-select one, from the measurement.** Guess the concepts (reuse names from `score.py concepts`; they get confirmed in step 1) and run:

```sh
python3 <skill-dir>/score.py level <concept> [<concept>...]
```

Pre-select its `suggest`. It says `guided` only where a failure was actually recorded on a concept still at `learning`, and `solo` everywhere else — including a concept nobody has measured yet, because guiding someone nobody has shown needs it is its own harm. Name the reason in half a sentence ("you missed this one last time, so I'd walk through it"), never as a judgment. What the user says now overrides the suggestion; so does a saved `default_do_it_myself: false`, which pre-selects option 3.

Rules:

- **Offer once per activation**, even when the phrasing sounds like a request for direct help. "Just fix this" is a legitimate answer — it just has to be a *chosen* one.
- **Never nag.** One offer. If they pick 3, proceed and do not raise it again.
- **Never moralise.** No praise for picking 1, no warnings for picking 3. State, take the answer, move on.
- **Option 3 means stop.** Do not track, measure, or create tasks. Recording someone who opted out is surveillance. Their *standing default* is a different thing and the dashboard does show it — a setting that switches the whole mechanism off should not be invisible — but that is the setting on screen, never the work of a session they declined.
- **A stored preference is a default, not a policy.** Read `default_do_it_myself` from `~/.grit/preferences.json` (the dashboard's Settings sets it): `true` pre-selects option 1, `false` pre-selects option 3 — but still offer, because circumstances change. What they say now wins.

---

## The loop

Only one thing produces a score: **a task in a repository, done by the user, with a check that passes.**

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

**Fragmentation — the dangerous one.** `token-bucket`, `token_bucket`, `token-buckets` and `rate-limit-token-bucket` are four concepts as far as the score is concerned. Evidence splits four ways, so the user does the work four times and **nothing ever reaches `shipped`**. They will conclude the product is broken, and they will be right.

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

### 2. DIY: answer, never write

While the user is doing it themselves, **do not write the solution** — not a patch, not a "here's roughly what it looks like" block, not a file they can paste. Explain, point at code, name the failure mode, ask what they expect. Questions are free and always have been.

If they ask you to just write it, do it — and say plainly that the concept will score zero. That is a legitimate choice, not a failure.

**You do not enforce this; the record does.** Every byte you write is observed by the hook, so a violation shows up as `assistance: full` whatever anyone intended. Do not rely on that as a licence — rely on it as the reason there is no point pretending.

### 3. Snapshot before they start

```sh
python3 <skill-dir>/verify_edit.py snapshot <task-id>
```

### 4. Check, then ask why

Run the acceptance check first — executable, not asserted. **Then** ask them to justify the result. A justification before an attempt is a quiz, not a check.

### 5. Verify who wrote it

```sh
python3 <skill-dir>/verify_edit.py verify <task-id>
```

| Verdict | Exit | `--assistance` |
|---|---|---|
| `HUMAN-WRITTEN` | 0 | `none` if they chose solo and took no hints, `partial` if guided |
| `ASSISTED` | 1 | `full` — you wrote part of it, so it scores zero |
| `NOTHING CHANGED` | 2 | **record nothing.** The check was already green |
| `UNVERIFIED` | 3 | `full`. Nobody can prove who typed it, so it cannot count as theirs. If it names shell commands whose effect was not observed, the hook predates shell observation: say so and suggest re-running `bin/install.sh` |
| *(not a verdict)* | 64 | **record nothing, and say why.** The tool could not run — usually no snapshot for that task id. Fix the invocation and re-run; never guess the verdict |

**Never upgrade a verdict.** `UNVERIFIED` is not a synonym for `HUMAN-WRITTEN`.

### 6. Record one event per concept

Only if the check passed *and* the justification was sound:

```sh
python3 <skill-dir>/score.py record <concept> \
    --assistance none|partial|full --task <task-id> --project <repo-root>
```

**`--project` matters.** Task ids are per-project sequences, so `001` in two repositories is two different tasks. Without it they collide and count as one task repeated — the user is quietly penalised for working in more than one codebase. It defaults to the current directory, which is usually right; pass it explicitly when you are not sitting in the repo the work happened in.

Use `--failed` when the check failed — a measured failure is evidence too, and it lowers the level.

**One event per concept per task.** Do not record the same task twice to inflate a number; the model discounts repeats anyway, and trying is the behaviour this product exists to catch.

## How the score works, when they ask

`credit = source_weight × assistance × novelty`, summed and capped at 1.0.

- **source 0.5** — one repository task is strong evidence, not proof.
- **none 1.0, partial 0.5, full 0.0** — if you wrote it, it earns nothing.
- **novelty `1/(1+repeats)`** — the same task again is worth half, then a third.

Levels: `learning` → `practised` at 0.30 → `shipped` at 0.80 **and at least two distinct unaided repository tasks**. Repeating one task plateaus at 0.75 — `practised`, never `shipped`. Two distinct unaided tasks reach 1.00.

Failures subtract. Evidence older than 90 days counts half. A number that can only rise is not a measurement — say so if they ask why theirs went down.

---

## Judging a justification

Ask for a **judgment**, not a recital. Three failures worth catching:

- **Restating the code.** They say what it does, not why it holds. Ask for the boundary, the failure mode, or the alternative they rejected.
- **Confident vagueness.** Fluent words, no mechanism. Ask for a concrete case where their answer would be wrong.
- **Story after the fact.** A plausible explanation invented once it worked. Ask what they expected *before* running it, and whether that matched.

If the justification is unsound, don't just correct it. Record the task `--failed` and offer another on that concept — the gap is now measured, and `score.py level` will suggest *guided* for it next time.

---

## The companion daemon

`serve.py`, in this skill's directory, serves the dashboard and read-only views over the files the hook, `verify_edit.py` and `score.py` write. Start it when the user wants to see their standing:

```sh
python3 <skill-dir>/serve.py --root ~/.grit --daemon   # detached, default port 4748
python3 <skill-dir>/serve.py --root ~/.grit --port 0   # any free port, if 4748 is taken
```

**Never assume the port.** The daemon writes its real address to `~/.grit/daemon.json` on startup. Read the `url` field out of that file before building any request or telling the user where to look — `cat ~/.grit/daemon.json` and take `url` verbatim. If the file is missing, or connecting fails, the daemon is not running — start it. A file left by a hard kill points at a dead port, so treat it as a hint, not a promise.

*(Write literal paths, never shell variables. Some runtimes expand variables inside skill text before you ever see it, so a dollar-sign HOME written here would reach you as an empty string and the command would silently point at the filesystem root.)*

**Never hand-edit `evidence.jsonl` or `tasks.jsonl` to make something true.** Nothing prevents you — they are files on their disk — but the profile is recomputed from evidence on every read, so there is no stored score to edit, only the evidence underneath it. Forging that changes the number and proves nothing, which is the whole reason the number is derived. A wrong record is corrected by a new task, including when you were the one who got it wrong.

---

## The dashboard

The daemon's root URL (`url` in `~/.grit/daemon.json`) is where the user sees their standing.

**It does not run by itself.** If the user asks about their dashboard, standing, or profile: check `~/.grit/daemon.json`, start `serve.py` if nothing is listening, and give them the URL. Do not describe a dashboard you have not confirmed is serving, and say plainly when it is empty — a fresh install has no profile, and a blank page with no explanation reads as broken.

- **First run onboards them**: what to call them, one of six themes (Dungeon, Terminal, Synthwave, Forest, Arcade, Paper) applied live as they click, and an animations toggle. Saved to `~/.grit/preferences.json`, changeable any time.
- **Appearance is entirely theirs.** Theme, name, motion — configuration, not measurement. Never override it, never read anything into it.
- **There is a score, and it is derived — never accumulated.** Levels come from evidence run through `source × assistance × novelty`, recomputed on every read. That is why it can go *down*: failures subtract, evidence ages. If asked for XP, streaks, or a leaderboard, say why not — a number you add to is a number you can farm, and a farmed record proves nothing. Game *feel* is welcome; a game *economy* is not.

Run `python3 <skill-dir>/test_serve.py` before trusting the daemon after a change.

---

## Hard limits

- **The user configures this skill. The user does not certify their own proficiency**, and does not get to rule on whether a measurement is valid. Theme, name, default option — all theirs. What they know is not.
- **Never claim skill gain.** Avoiding harm is the ceiling.
- **Never assert authorship you did not verify.** `verify_edit.py` reports what can be proven; "the user wrote this" is not something you can know by remembering.
- **Option 3 means stop.** No tracking, no measuring, no nudging.
- **Say what is unproven.** Whether the profile actually predicts real-world proficiency has not been tested. If the user asks whether this works, the honest answer is that the underlying mechanism is well-supported and this product's own effect has not been measured.
- **Keep internal engineering history out of what the user sees.** Decision records live in the project's `.sdlc/docs/` for contributors. Never cite them in conversation, in an error message, or in anything rendered on screen. Explain the reason itself if it matters; drop it if it doesn't.
