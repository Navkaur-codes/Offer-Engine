# progress.md: version → phase → session log

> **Append-only.** Every session adds an entry at the end of its work, using the template at the bottom.
> The main session updates the version/phase status tables at every phase gate.
> Status key: ☐ not started · ◐ in progress · ☑ done · ⛔ blocked

## Version status
| Version | Target | Milestone | Status |
|---|---|---|---|
| v0.1 | Thu 22 Oct | Scaffold + contracts + bot "hello" deployed, link shared | ☑ |
| v0.2 | Fri 23 Oct | `/simulate cart` end-to-end (decision → validator → Telegram → log) | ◐ |
| v0.3 | Sat 24 Oct | Dashboard live on the real API (Overview, Decisions, Rules) | ☐ |
| v0.4 | Sun 25 Oct | Uplift + holdout + Customer Lab + Experiments + Playground | ☐ |
| v1.0 | Mon 26 Oct 18:00 | Feature freeze, classmate test round done, README done | ☐ |
| Submit | Tue 27 Oct ≤ 10:00 | Repo + bot username submitted | ☐ |

## Phase status per session
| Session | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| Main (Step 0 + gates + API + deploy) | ☑ Step 0 · ◐ watch P1 | ☐ | ☐ | ☐ |
| A: Data & Scoring | ☐ | ☐ | ☐ | ☐ |
| B: Decision Core | ☐ | ☐ | ☐ | ☐ |
| C: Telegram + Lab | ☐ | ☐ | ☐ | ☐ |
| D: Dashboard | ☐ | ☐ | ☐ | ☐ |

## claude-progressive.md history
| Version/Phase | Written | Summary of temporary rules |
|---|---|---|
| v0.1 / Phase 0 | 22 Oct | Scaffold only; contracts may change until the gate |
| v0.2 / Phase 1 | 22 Oct | Contracts v1 frozen; everything through ports/stubs; never poll with the prod token; shared venv; no real Groq calls |

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

### 2026-10-22 · Main · Step 0 foundation + deploy (GATE-0)
- **Version/Phase:** v0.1 / Phase 0. Done; gate passed.
- **Did:**
  - Scaffold, contracts v1 (frozen), config with IST clock and time-travel, db with 13 tables, ports and stubs (21 ports).
  - FastAPI `/health` and a secured webhook; hello bot; Dockerfile and render.yaml.
  - Deployed to Render (https://offer-engine-n4jx.onrender.com) on Neon, with the cron-job.org ping.
  - One-page status report: `docs/reports/status-v0.1.pdf`.
- **Fixes:** blank `.env` values crashed startup; the bot token was leaking into httpx logs.
- **Commits:** a73db39 initial docs · ee4c27a scaffold + contracts · 98fa675 config/db/models · 263d388 ports/stubs · b8d28ce entrypoint/webhook/bot/deploy · 3cb8857 env + log fix
- **Tests:** `python -m pytest -q` (backend) → 19 passed · ruff clean · live `/health` 200 · wrong-secret webhook 403
- **Open issues / risks:**
  - LLM budget guard awaits a decision.
  - Lab bots still to create (by Sun).
  - Session C needs a dev bot.
- **Next:** the user creates the branches and worktrees, then starts sessions A1–D1.

### 2026-10-24 · Main · Design system changed: Ledger → Signal
- **Version/Phase:** v0.2 / Phase 1 (before any session started)
- **Why:** Ledger's warm paper/beige palette was too close to the user's Hackathon 1 skin-tone UI. The user also wants a general, modern look with no regional theming.
- **Did:**
  - The new "Signal" system: cool monochrome, dark sidebar, one orange accent `#FF4F00`, violet second series, amber warnings, Geist + Geist Mono.
  - Signature elements: Decision Pipeline Lens, bento Overview, terminal-style stream.
- **Files:** `CLAUDE.md §7`, `docs/PLAN.md §7`, `docs/context/context-4.md`, `docs/context/context-3.md` (card image), `docs/prompts.md` (D1), `docs/detective.md` (T06), `docs/claude-progressive.md`
- **Next:** the user fast-forwards all 4 feature branches to main, then starts sessions A1–D1.

### 2026-10-24 · Session A · Phase 1: personas, catalogue, festival calendar, generator, seed (A1)
- **Version/Phase:** v0.2 / Phase 1. Done; all "Done when" items met.
- **Did:**
  - `personas.py`: the 9 personas with visit/funnel rates, AOV multiplier, discount use, return propensity, churn hazard, festival sensitivity and hidden response-type mix (deal_hunter 50/30/15/5).
  - `catalog.py`: 10 categories with margin, lognormal AOV, price band, return rate and shipping cost, plus 120 products with Indian names and ₹ prices.
  - `festivals.py`: 26 festivals Sep 2025 – Jan 2027 with phases, hero categories, greeting, opt-in, restricted promos, budget, delivery days and per-phase lift multipliers. The 2026 dates were checked against SmartPuja's 2026 calendar and the gazetted list (sources in the file comment).
  - `generator.py`: a seeded day-by-day simulation of 1 Oct 2025 → yesterday. It covers a Punjab-heavy city mix (~45%), a signup curve, the hour-of-day curve, the session → view → cart → checkout → purchase funnel, lognormal order values matched to real products, returns (COD returns more), points with 180-day expiry, tiers, festival and payday lifts, a churn hazard, and messy data (3% missing age, 4% missing gender, duplicate session beacons, heavy returners).
  - 6 past campaigns, including **Diwali 2025**, with a random 10% control. Outcomes follow the hidden response type: persuadable uplift ≈ +0.14, sure-thing ≈ 0, sleeping dog negative.
  - `seed.py` CLI: `python -m app.data.seed --customers 5000 --seed 42 [--end YYYY-MM-DD]`. It writes about 766k events, 15k orders, 21k points rows, 7.4k campaign rows, 120 products and 26 festivals in about 35 s on SQLite, and it can be re-run.
  - `stats.py`: realism metrics plus `BENCHMARKS` with sources, ready for `scoring.realism` in Phase 3.
- **Benchmarks (seed 42):** Pareto top-20% 0.76 · cart abandonment 0.70 · view→purchase 3.1% · fashion returns 0.26 · Diwali week 2.3× · evening sessions 42%.
- **Files:** `backend/app/data/{personas,catalog,festivals,generator,stats,seed}.py`, `backend/tests/data/{test_generator_stats,test_seed_and_calendar}.py`, `docs/sessions.md` (row A + notes), `docs/progress.md`
- **Commits:** _pending the user's commit_
- **Tests:** `python -m pytest tests -q` (backend) → 54 passed (35 in `tests/data`, 2 seeds) · `ruff check .` clean
- **Open issues / risks:** Lohri 2027 has conflicting sources (13 vs 14 Jan); re-check in January. Seeding Neon over the network will be slower than SQLite; seed locally or with fewer customers if it is slow.
- **Contract change requests:** none
- **Next:** Phase 2: `scoring/rfm.py`, `scoring/churn.py`, `scoring/profile.py` (`build_profile` under 50 ms, `assign_policy`), `data/onboarding.py`.
