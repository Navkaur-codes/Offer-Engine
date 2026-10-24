# claude-progressive.md: current phase instructions

> This file is **rewritten by the main session before every phase**. It is imported by the root `CLAUDE.md`, so it applies to every prompt.
> Permanent rules stay in `CLAUDE.md`. This file only holds *what is true right now*.
> Keep it under 80 lines. Past versions of this file are summarised in `docs/progress.md`.

---

## Now
- **Version:** v0.3 (target Sun 25 Oct, 12:00). The schedule is compressed because we're about a day behind.
- **Phase:** 2. Sessions A–D work in parallel in their worktree folders; Main builds the REST API (MAIN-API).
- **GATE-1 passed (24 Oct).** `main` has all four Phase-1 merges. 118 backend tests pass and the frontend builds.
- **Live:** https://offer-engine-n4jx.onrender.com, bot `@navpreet_offers_bot`. Neon is seeded with about 1,500 synthetic customers (production uses fewer than 5,000 because of Neon's free 0.5 GB limit).
- **Contracts:** **v1 FROZEN.** Changes only through `sessions.md → Contract change requests`.
- **Real ports now:** `seed_run`, `festivals`, `effective_policy`, `allowed_offers`, `evaluate`, `describe_rule`, `deliver`, `build_application`, `set_bot_commands`. Everything else is still a stub. Check with `ports.status()` or `/health`.
- **Next gate:** GATE-2, which must show `/simulate cart` working end-to-end on the live bot: event → real profile → harness → `evaluate` → card → decision log → `/why`.

## Phase-2 goals (details in each context file)
- **A:** `scoring/rfm.py`, `churn.py`, `profile.py` (`build_profile` < 50 ms from real DB rows, `assign_policy`), `data/onboarding.py` (`create_profile_from_answers`).
- **B:** `agent/context.py`, `harness.py` (full pipeline, pre-gate reads `opted_out` / `paused_until`, holdout, dry_run), `fallback.py`, `llm.py` (MockLLM), `explainer.py`. **Never call `deliver()` from `decide()`**, because the bot sends the card itself.
- **C:** `/simulate …` commands, recorded button outcomes (claim / decline → 14-day suppression), `/why`, `/history`, per-user rate limit.
- **D:** Overview (bento, live stream) and Decisions log (Pipeline Lens, explanation drawer) on mocks. Switch to the real API as soon as MAIN-API lands.
- **Main:** `app/api/` endpoints from `contracts.md §4` (starting with kpis, decisions, customers, rules, playground), the admin passcode guard, CORS, and calling `seed_rules.ensure_seeded()` at startup.

## Temporary rules for this phase
- Notes from sessions in `sessions.md §7` are binding. Key ones:
  - festival opt-in keys come without the year (`diwali`);
  - offer params are `pct`, `amount`, `min_basket`, `multiplier`, `category`;
  - seeded `C000001…` customers are **not** the stub fixtures.
- **Never run `--polling` with the production bot token.** C uses the dev bot in its worktree `.env`.
- **Python:** use the shared venv `D:\hackathon-2\.venv\Scripts\python`, and run `-m pytest` from *your* worktree's `backend/`.
- **LLM budget:** still no real Groq calls (B uses MockLLM). The decision on the budget guard is still pending with the user.
- 📌 Give a commit checkpoint after every finished task. The user commits, pushes and merges.
- End every phase with a `docs/progress.md` entry **in your own branch** (D forgot this in Phase 1).

## Known issues / decisions pending
- **LLM budget guard** (single-call agent, daily token budget, 70B → 8B → rules fallback) is awaiting the user's OK before B3.
- **Customer Lab bots** (10 bots, the "Customer Lab" group, the shadow channel) are needed by Sun, before C3.
- D: Lighthouse score not measured yet; the 615 kB bundle needs code-splitting in Phase 4.
- C: the phone check of `/start` on the dev bot is pending with the user.

## Worktree folders
| Session | Folder | Branch |
|---|---|---|
| Main | `D:\hackathon-2` | `main` |
| A | `D:\offer-engine-A` | `feat/data-scoring` |
| B | `D:\offer-engine-B` | `feat/decision-core` |
| C | `D:\offer-engine-C` | `feat/telegram-lab` |
| D | `D:\offer-engine-D` | `feat/dashboard` |
