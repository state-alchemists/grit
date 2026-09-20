# ADR 0006 — Two credentials per session: the page reports, the assistant judges

- **Status**: Accepted
- **Date**: 2026-09-13 (revised 2026-09-14)
- **Deciders**: Go Frendi
- **Context tags**: completion, daemon, integrity, security, gates

## Context

ADR 0005 gave the daemon its reason to exist: *"the page never writes the ledger; only this process does."* The first implementation held that sentence literally and lost it in practice.

The daemon minted **one** session token per tutorial launch and injected it into the page as `window.GRIT_SESSION`. All three gates were then reachable at `POST /tutorial/<token>/<gate>` — including `judgment`. The page could not write `ledger.json` with its own hands, but it could make the daemon write any row it liked, `earned: true` included, with a single `fetch()`.

Reproduced against the shipped daemon:

```
1. check pass          -> earned: False
2. justification       -> earned: False
3. PAGE self-judges    -> earned: True      ← one fetch() from the sandbox
```

Three further defects shared the same root — one secret doing several jobs, and `earned` being asserted rather than derived:

- `judge()` set `earned = judgment == "sound"` without consulting the check, so re-reporting a failed check afterwards left a row claiming `earned: true` beside `check.passed: false`.
- Ledger rows carried the **raw session token** in their `session` field, and `/ledger` echoed any `http://localhost:*` origin. Every `npm run dev` on the machine could read the whole ledger — every concept failed, every justification verbatim — and then mint judgments from the tokens it found there. That is exactly the liability DESIGN §8 exists to prevent; loopback is not a boundary on a developer's machine, it is the least isolated address on it.
- Sessions were RAM-only. Gate 3 arrives whenever the assistant gets to it, so a restart in that window stranded the concept permanently unearned, fixable only by hand-editing the ledger — which ADR 0009 forbids.

The split still left one door open, which real use soon closed. Keeping the page away from gate 3 stopped there, and the verdict itself stayed mutable: `judge()` overwrote `session["judgment"]` on every call with no history. A judgment cast with the placeholder message `"test"` was then re-cast with the real reasoning, and the ledger kept no trace of the first. A record whose whole claim is that it cannot be talked out of was quietly rewriting itself — the same class of defect as the page awarding its own judgment, one layer further in.

## Decision

**Two credentials per session, on separate routes.**

| Credential | Goes to | Buys |
|---|---|---|
| **report token** | injected into the page | `POST /tutorial/<report>/check`, `.../justification` |
| **judge token** | printed to the daemon's stderr | `POST /judgment/<judge>` |

`POST /tutorial/<report>/judgment` returns **403**, not 404 — the page attempting to judge itself is the attack this split exists to stop, and it should be legible in the log rather than look like a typo.

Four supporting rules:

1. **`earned` is derived, never assigned.** One function, `_earned(session)`: all three gates present, the check actually passed, the judgment sound. It is now impossible for two code paths to disagree about what earned means, because there is one.
2. **No raw credential enters the ledger.** Rows carry a short opaque `sid`. CORS is closed outright — every page that talks to the daemon is a page the daemon served, so same-origin suffices and no cross-origin reader is contemplated.
3. **Sessions persist** to `sessions.json` at mode `0600`, so a pending judgment survives a restart.
4. **The first verdict stands.** Nothing re-judges a session, not even a second cast from the same judge token. A later call appends to the `judgments` history, returns `409` with the standing verdict and the full list, and changes neither the gates nor `earned`. The remedy for a wrong verdict is a fresh attempt at the tutorial, which opens a new session and writes new evidence. Editing the past is the one operation this ledger exists to prevent, and "the assistant made a mistake" is not an exemption — it is the exact case an audit trail is for.

## Consequences

- ADR 0005's guarantee is now mechanical rather than stated. The page cannot reach gate 3 with anything it holds.
- **The judge token must reach the assistant out of band.** Today it is printed to stderr and the assistant runs the `curl` line. This is the honest seam in the design: it works, and it is clearly a v1 mechanism rather than a finished one.
- Anything that talked to the daemon cross-origin stops working. The tutorial template now uses a same-origin relative URL when the daemon served it, and the absolute fallback only applies to a hand-opened `file://` page.
- `sessions.json` holds live credentials in plaintext under `~/.grit/`. It is mode-`0600` and never transmitted, which is the same boundary the ledger already relies on — one more file inside it, not a new exposure.
- **The lesson generalises past this bug.** A guarantee written in a docstring is a claim; this repository's whole thesis is that claims are not measurements. `skills/grit/test_serve.py` now pins all six properties, and every case in it is a defect that actually shipped while the README described the daemon as "working and tested."
- **The first verdict is pinned to the incident that made it.** `test_serve.py`'s gate-3-appends property replays the real sequence — cast `unsound/"test"`, then attempt `sound/"real reasoning"` — and asserts the standing verdict is still `unsound/"test"`, that both verdicts are retained, and that `earned` did not flip.

## Rejected

- **One token, and trust the page not to call the judgment route.** This is ADR 0011's rejected self-report wearing a different hat, and it fails for the same reason: the party being measured should not hold the instrument.
- **Signing the judgment payload.** Any key the page could verify, the page could also use.
- **Keeping permissive localhost CORS and adding a bearer token to `/ledger`.** Strictly more moving parts than closing CORS, for a cross-origin capability nothing needs.
- **Letting a re-judgment replace the verdict when it comes from the same judge token.** The token proves who is calling, not that the second answer is better than the first. Under that rule the `"test"` incident is indistinguishable from a deliberate rewrite.
- **Recording a compensating evidence row so the score follows the latest verdict.** Double-entry bookkeeping would keep the history honest, but `unsound` then `sound` nets to a different number than a clean `sound`, so the score would depend on how many times someone changed their mind. A frozen first measurement is simpler and truer.
