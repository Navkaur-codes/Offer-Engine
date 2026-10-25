# claude-progressive.md: current phase instructions

> This file is **rewritten by the main session before every phase**. It is imported by the root `CLAUDE.md`, so it applies to every prompt.
> Permanent rules stay in `CLAUDE.md`. This file only holds *what is true right now*.
> Keep it under 80 lines. Past versions of this file are summarised in `docs/progress.md`.

---

## Now
- **Version:** v0.4 (target Sun 25 Oct, night). The freeze is **Mon 26 Oct 18:00**.
- **Phase:** 3, **in progress since 25 Oct.** Sessions A–D work in parallel. Main has the scheduler live (`/api/scheduler`: abandoned carts, 09:05 queue flush, points expiry, 21:00 digest).
- **GATE-2 passed (25 Oct).**
  - `main` has all Phase-2 merges; 214 backend tests pass and the frontend builds.
  - **Production runs the real pipeline:** onboarding → real profile → harness → `evaluate` → card → decision log.
  - The `TG…` BIGINT fix is live.
- **Live:** https://offer-engine-n4jx.onrender.com (API v0.3, contracts v1.1), bot `@navpreet_offers_bot`, Neon with about 1,500 seeded customers.
- **Still stubs:** `uplift_predict`, `impact_estimate`, `realism_compute`, `experiments_compute`, `daily_digest`, `rule_impact`, `run_rounds`. Check with `/health`.
- **Next gate:** GATE-3. Needs real offers going to classmates (not "No offer" for everyone), the Lab running in the group, and the dashboard on Vercel with real data.

## 🔴 PRIORITY 1 for Phase 3: "No offer for everyone"
Found live at GATE-2: every decision is NO_OFFER, because uplift is a ~0.04 prior and impact is a stub.
- **A:** real `uplift.py` and `impact.py` first, as their own checkpoint.
- **B:** zero-cost offers allowed at profit ≥ 0, plus the welcome guarantee, first, as their own checkpoint.

Both are detailed at the top of each session's Phase 3 in its context file. Nothing else in A or B ships before these.

## Phase-3 goals (details in each context file)
- **A:** uplift T-learner + Qini, impact, realism stats, experiment stats.
- **B:** priority fix; then the real Groq agent with the **single-call design**, `agent/budget.py` (70B → 8B at 80% → rules at 100%), the top-5 batch rule, and the message + festival_restriction validators.
- **C:** Customer Lab: 10 fixed Lab customers voiced round-robin by 1–10 bots (the user has **4**: "Lab Shopper 1–4"), each post starting with "👤 Name · persona"; `/lab here | run | who | persona <name> | date | reset`. There is no shadow channel. Also verify `/simulate` against the real harness on the dev bot.
- **D:** switch to the real API and contracts v1.1; Rules editor (sentence cards, impact preview, versions/revert); Customers (scatter, drawer, simulate); Vercel deploy.
- **Main:** watch the gates, answer contract requests, deploy, set `CORS_ORIGINS` for Vercel.

## Temporary rules for this phase
- Notes in `sessions.md §7` are binding:
  - festival keys don't include the year;
  - offer params are `pct`, `amount`, `min_basket`, `multiplier`, `category`;
  - write decisions only via `decision_store`;
  - quiet hours apply to proactive sends only (`runtime.quiet_hours_apply`).
- `tests/conftest.py` pins other sessions' ports to stubs in your unit tests. To test against real modules, mark the test `@pytest.mark.real_ports`.
- **Never** run `--polling` with the production token. C uses the dev bot.
- **Real Groq calls** are allowed from B3 on, but only through `agent/budget.py`. Keep the 20 test runs small.
- 📌 Give a checkpoint after every finished task, and record progress in your own branch.
- Use BIGINT for any external ID column (detective T29). Postgres is stricter than SQLite.

## Known issues
- D: Lighthouse score not measured yet; the ~620 kB bundle needs code-splitting in Phase 4.
- Real Telegram users get `is_holdout=False` (A's choice, so classmates never get a silent bot). Synthetic customers keep the 10% holdout.

## Worktree folders
| Session | Folder | Branch |
|---|---|---|
| Main | `D:\hackathon-2` | `main` |
| A | `D:\offer-engine-A` | `feat/data-scoring` |
| B | `D:\offer-engine-B` | `feat/decision-core` |
| C | `D:\offer-engine-C` | `feat/telegram-lab` |
| D | `D:\offer-engine-D` | `feat/dashboard` |
