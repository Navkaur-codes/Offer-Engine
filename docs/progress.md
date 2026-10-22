# progress.md: version → phase → session log

> **Append-only.** Every session adds an entry at the end of its work, using the template at the bottom.
> The main session updates the version/phase status tables at every phase gate.
> Status key: ☐ not started · ◐ in progress · ☑ done · ⛔ blocked

## Version status
| Version | Target | Milestone | Status |
|---|---|---|---|
| v0.1 | Thu 22 Oct | Scaffold + contracts + bot "hello" deployed, link shared | ◐ |
| v0.2 | Fri 23 Oct | `/simulate cart` end-to-end (decision → validator → Telegram → log) | ☐ |
| v0.3 | Sat 24 Oct | Dashboard live on the real API (Overview, Decisions, Rules) | ☐ |
| v0.4 | Sun 25 Oct | Uplift + holdout + Customer Lab + Experiments + Playground | ☐ |
| v1.0 | Mon 26 Oct 18:00 | Feature freeze, classmate test round done, README done | ☐ |
| Submit | Tue 27 Oct ≤ 10:00 | Repo + bot username submitted | ☐ |

## Phase status per session
| Session | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| Main (Step 0 + gates + API + deploy) | ◐ Step 0 | ☐ | ☐ | ☐ |
| A: Data & Scoring | ☐ | ☐ | ☐ | ☐ |
| B: Decision Core | ☐ | ☐ | ☐ | ☐ |
| C: Telegram + Lab | ☐ | ☐ | ☐ | ☐ |
| D: Dashboard | ☐ | ☐ | ☐ | ☐ |

## claude-progressive.md history
| Version/Phase | Written | Summary of temporary rules |
|---|---|---|
| v0.1 / Phase 0 | 22 Oct | Scaffold only; contracts may change until the gate |

## Detective overrides
_none yet_ (format: `date · trap ID · session · reason`)

---

## Session log

### 2026-10-22 · Main · Planning
- **Version/Phase:** v0.1 / Phase 0 (planning)
- **Did:**
  - Read the brief.
  - Agreed the plan v2: analytics + agentic decisioning platform, layered dynamic rules, festival-aware offers, Customer Lab with 10 bots, Ledger design, free hosting (Render + Vercel + Neon), Groq.
- **Files:**
  - `CLAUDE.md`
  - `docs/PLAN.md`, `docs/claude-progressive.md`, `docs/progress.md`, `docs/sessions.md`, `docs/detective.md`, `docs/contracts.md`, `docs/prompts.md`
  - `docs/context/context-1..4.md`
- **Commits:** none yet (no git repo yet)
- **Open issues:**
  - Verify the 2026 festival dates.
  - Create the BotFather bots (Offer bot + 10 customer bots).
  - Get a Groq key, and create Neon/Render/Vercel accounts.
- **Next:** Step 0 in the main session (see `prompts.md → MAIN-0`).

---

<!-- TEMPLATE: copy below, fill, append at the end
### YYYY-MM-DD · <Session A|B|C|D|Main> · <short title>
- **Version/Phase:** vX.Y / Phase N
- **Did:** bullet list of finished work (what a judge could see)
- **Files:** paths touched
- **Commits:** short hashes + messages
- **Tests:** command + result (e.g. `pytest backend/tests/core -q` → 42 passed)
- **Open issues / risks:**
- **Contract change requests:** (also add to sessions.md)
- **Next:** first task for the next phase
-->
