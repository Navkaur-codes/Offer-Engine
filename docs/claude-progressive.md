# claude-progressive.md: current phase instructions

> This file is **rewritten by the main session before every phase**. It is imported by the root `CLAUDE.md`, so it applies to every prompt.
> Permanent rules stay in `CLAUDE.md`. This file only holds *what is true right now*.
> Keep it under 80 lines. Past versions of this file are summarised in `docs/progress.md`.

---

## Now
- **Version:** v0.2 (target Fri 23 Oct, 23:59)
- **Phase:** 1. Sessions A–D work in parallel, each in its own worktree folder.
- **Live backend:** https://offer-engine-n4jx.onrender.com. `/health` is green, the bot is on, the hello `/start` works, and cron-job.org pings every 10 min.
- **Contracts:** **v1 FROZEN.** Changes only through `sessions.md → Contract change requests`.
- **Next gate:** GATE-1. Needs all four sessions' Phase-1 "Done when" items met, plus `/simulate cart` working end-to-end by the end of v0.2.

## Phase-1 goals (details in each context file)
- **A:** personas, catalogue, verified 2026 festival calendar, 12-month generator, past campaigns, seed CLI, generator-stats tests.
- **B:** rule types + seed rules (4 layers), `engine.effective_policy / allowed_offers / evaluate`, property test.
- **C:** onboarding `/start`, render cards, `/profile /help /offers /pause /stop`, using stub `decide`.
- **D:** Vite scaffold, Ledger theme, app shell, ⌘K, kill switch, typed API client + mocks, shared components.
- **Main:** watch `sessions.md`, answer contract requests, start the `app/api/` skeleton (MAIN-API) once A or B has something real.

## Temporary rules for this phase
- Everything that belongs to another session comes from `app.ports`. Stubs are deterministic: `C000003`/vip gives NO_OFFER, trigger `manual` gives BLOCKED, everything else gives SENT.
- **Never run `--polling` with the production bot token.** Session C uses a separate dev bot in its worktree `.env`.
- Worktree folders have no `.env`, because it's gitignored. Copy one in only if you need it (C for the dev bot; others don't).
- **Python:** use the shared venv, `D:\hackathon-2\.venv\Scripts\python`, and run `-m pytest` from *your* worktree's `backend/` folder. Running from there imports your local `app` code, not the main checkout's.
- **LLM budget:** no real Groq calls in Phase 1. B builds the engine only; tests use mocks.
- 📌 Give the user a commit checkpoint after every finished task. The user commits, pushes and merges.

## Known issues / decisions pending
- **LLM budget guard** (single-call agent design, daily token budget, 70B → 8B → rules fallback): proposed and awaiting the user's OK. If accepted, it gets added to context-2 Phase 3.
- **Customer Lab setup** (10 customer bots, "Customer Lab" group, shadow channel) is due by Sun, before C3.
- Festival dates must be checked (A1).

## Worktree folders
| Session | Folder | Branch |
|---|---|---|
| Main | `D:\hackathon-2` | `main` |
| A | `D:\offer-engine-A` | `feat/data-scoring` |
| B | `D:\offer-engine-B` | `feat/decision-core` |
| C | `D:\offer-engine-C` | `feat/telegram-lab` |
| D | `D:\offer-engine-D` | `feat/dashboard` |
