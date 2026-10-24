# sessions.md: overview of all sessions and integration health

> This is the control tower. Each session updates **only its own row** and adds notes. The **main session** runs the gate checklist and health log, and decides on contract change requests.

## 1. Session board
| Session | Branch / worktree | Context file | Current phase | Status | Contract ver. | Blockers | Last update |
|---|---|---|---|---|---|---|---|
| Main / Integrator | `main` · `D:\hackathon-2` | `CLAUDE.md`, `docs/PLAN.md` | GATE-1 passed → Phase 2 (+ MAIN-API) | ☑ P0 ☑ GATE-1 | v1 frozen | none | 24 Oct |
| A: Data & Scoring | `feat/data-scoring` · `D:\offer-engine-A` | `docs/context/context-1.md` | Phase 1 done (A1) → Phase 2 next | ☑ P1 (`8b2e903`) | v1 | none | 24 Oct |
| B: Decision Core | `feat/decision-core` · `D:\offer-engine-B` | `docs/context/context-2.md` | Phase 1 done (rules engine) → Phase 2 next | ☑ P1 (`0202dd8`) | v1 | none | 24 Oct |
| C: Telegram + Lab | `feat/telegram-lab` · `D:\offer-engine-C` | `docs/context/context-3.md` | Phase 1 done (53 tests green) → Phase 2 next; phone check of `/start` on the dev bot still pending | ☑ P1 (`1e5e102`) | v1 | none (dev bot `@navpreet_offers_dev_bot` in worktree `.env`) | 24 Oct |
| D: Dashboard | `feat/dashboard` · `D:\offer-engine-D` | `docs/context/context-4.md` | Phase 2 done (Overview bento + live SSE stream, Decisions filters + drawer); checked against the local real API; Lighthouse not yet measured | ☑ P1 (`e5d9116`) · ☑ P2 (`a9aa536` + D2b) | v1 | CR-D1, CR-D2 open; real decisions need B's harness | 24 Oct |

## 2. Dependency map (who consumes whom; always through `app.ports` with stubs)
```
A (data/scoring) ──profile, uplift, impact, festivals──► B (rules/agent) ──decide(), explain()──► C (bot/lab)
        │                                                     │                                   │
        └──────── realism, experiments ────────► Main API ◄───┴── decisions, rules ───────────────┘
                                                    │
                                                    ▼
                                              D (dashboard)
```
**Merge order at each gate:** A → B → C → D → Main API wiring. After each merge, swap the stub for the real module in `ports.py`.

## 3. Phase gate checklist (main session runs this; see `prompts.md → GATE-N`)
> **The user does all git writes** (commit, push, merge). The main session gives the exact commands one step at a time and checks each result.
- [ ] Every session's branch has its phase "Done when" items met (check its context file) and its tests green on its branch.
- [ ] Every 📌 checkpoint for the phase is confirmed "committed" **and pushed** (`git log origin/<branch>` shows it).
- [ ] The user merges into `main` in the order above, following the main session's commands one branch at a time. Resolve conflicts. Conflicts should only appear in `progress.md`/`sessions.md`; anything else means a boundary was broken, so log it.
- [ ] `pytest backend/tests -q` and `ruff check backend` are green on `main`. `cd frontend && npm run build` is green.
- [ ] In `ports.py`, replace the stubs with the merged real modules, then run the integration smoke test (below).
- [ ] Deploy (Render + Vercel) and check `/health`, `getWebhookInfo`, and that the dashboard loads real data.
- [ ] Update the health log (§5), the version/phase tables in `progress.md`, and **rewrite `claude-progressive.md`** for the next phase.
- [ ] Rebase or merge `main` back into each feature branch so every session starts the next phase up to date.

## 4. Integration smoke test (run after every gate)
1. `python -m app.data.seed --customers 500 --seed 1` completes.
2. `POST /api/playground/run` for 5 fixture customers (one per main policy) returns a valid `Decision` with an `explanation`.
3. Telegram: `/start` gives a welcome card. `/simulate cart` gives a card. `/why` gives the explanation. `/simulate purchase` then `/simulate cart` gives NO_OFFER with the 48 h reason.
4. Kill switch ON, then `/simulate cart` gives BLOCKED. Turn it OFF again.
5. Force an LLM failure (env `FORCE_LLM_FAIL=1` or the Playground toggle) and check the RULES_FALLBACK decision is still compliant.
6. The dashboard Decisions page shows all of the above, with correct badges.
7. (From v0.4) `/lab run 3` in the Lab group gives 3 readable exchanges.

## 5. Health log (newest first)
| Date/time | Gate | Tests | Deploy | Smoke test | Notes |
|---|---|---|---|---|---|
| 24 Oct 20:01 | GATE-1 | `pytest` 118 passed · ruff clean · frontend lint + build ✓ | pending (push main) | scratch seed of 500 customers in 7 s ✓; real rules: 50% off blocked, 10% + ₹999 allowed ✓; stub decide gives SENT / NO_OFFER / BLOCKED ✓; app boots, 8/21 ports real (+ `set_bot_commands`) | merges `948bcb1` A · `90670b6` B · `9bd7391` C · `62a4065` D; only progress/sessions docs conflicted (resolved, all entries kept); the stub test was updated for the real ₹999 deal-hunter rule |
| 22 Oct 17:38 | GATE-0 | `pytest` 19 passed · ruff clean | Render live: `/health` ok, bot true, 0.8 s | wrong-secret webhook returns 403 ✓; `/start` hello (user) ✓ | all 21 ports are stubs except `build_application` |

## 6. Contract change requests
Format: `ID · date · from session · what change · why · status (open/accepted/rejected) · contract version`
- _none yet_
- CR-D1 · 24 Oct · D · `Kpis.deltas`: use the same keys as the `Kpis` fields (`sent_today`, `claim_rate`, `incremental_revenue`, `budget_used_pct`, `blocked_by_rules`, `margin_saved`), with values as a fractional change vs yesterday (`0.12` = +12%). The API currently sends `{"sent","claim_rate","blocked"}` and it's unclear whether those are absolute or relative. · The KPI strip shows ▲▼ per tile and can't map the current keys without guessing. · open · v1
- CR-D2 · 24 Oct · D · Add `festival: str | None` to `DecisionLight` and a `festival=` filter to `GET /api/decisions`. · context-4 Phase 2 asks for a festival filter on the Decisions log; today only `trigger=festival` exists, which misses festival-phase decisions from other triggers. · open · v1

## 7. Notes for other sessions
Format: `date · from → to · note`
- 22 Oct · Main → all · Live backend: https://offer-engine-n4jx.onrender.com. `/health` shows which ports are `stub` and which are `real`.
- 22 Oct · Main → all · Stubs are deterministic: `C000003`/vip gives NO_OFFER, trigger `manual` gives BLOCKED, everything else gives SENT. There are 5 fixture customers, `C000001`–`C000005`.
- 22 Oct · Main → all · Implement exactly the module path and function name from `contracts.md §3`, and the port flips to real on its own.
- 22 Oct · Main → C · `bot/app.py` is a Phase-0 hello; replace it. **Never poll with the production token.** Use a dev bot.
- 22 Oct · Main → all · Use the shared venv `D:\hackathon-2\.venv`. Run `python -m pytest` from your worktree's `backend/` folder.
- 24 Oct · A → B, C · `Customer.opt_in_festivals` holds festival **keys** (`"diwali"`, `"gurpurab"`, …), not yearly ids. Match a festival with `app.data.festivals.festival_key("diwali_2026") == "diwali"`. Valid keys are in `festivals.OPT_IN_KEYS`. Every festival with a greeting has `needs_opt_in=True`; commercial sales (Black Friday, Republic Day, wedding season) have no greeting.
- 24 Oct · A → B · `FESTIVALS` has 26 rows for Sep 2025 – Jan 2027, with 2026 dates verified (sources in `festivals.py`). `restricted_promos` are lowercase keywords (`meat`, `alcohol`, `egg`, `tobacco`, …) for the message validator. Phase offsets overlap for Dhanteras/Diwali/Bhai Dooj, so pick the festival with the nearest `date` when several are active.
- 24 Oct · A → all · `python -m app.data.seed` replaces only synthetic customers (`C…`) and their rows. Real Telegram users (`TG…`), decisions and rules survive a re-seed, and customers a Lab bot points to are updated in place. Seeded ids `C000001…` are **not** the stub fixtures (different names/personas). Seeding 5,000 customers on SQLite takes about 35 s.
- 24 Oct · B → Main · The real `rules.engine` makes `tests/api/test_ports.py::test_evaluate_flags_over_limit_discount` fail: a deal hunter needs `min_basket ≥ 999`, and a missing `min_basket` counts as 0. Please change that case to `{"pct": 10, "min_basket": 999}` when merging B.
- 24 Oct · B → Main/A · Rules are read from the `rules` table, falling back to `SEED_RULES` when it's empty. Call `app.rules.seed_rules.ensure_seeded()` from the seed CLI or at startup. The catalogue is read from the `offers` table, falling back to `stubs.CATALOGUE`.
- 24 Oct · B → A · Offer param names the engine understands: `pct`, `amount` (flat ₹), `min_basket`, `multiplier`, `category`. Please use these in the catalogue.
- 24 Oct · B → C/D · `evaluate(profile, ctx, None, {})` is the pre-gate check, and `RuleCheck.description` is always the live `describe()` sentence. `screen_offers()` also returns the rejected offers with plain-English reasons, ready for "alternatives rejected".
- 24 Oct · C → A · `create_profile_from_answers` gets `answers = {"categories": [Category], "frequency": "weekly|monthly|occasionally|rarely", "style": "deal|quality|balanced", "festivals": ["diwali","gurpurab","lohri","karwa_chauth","christmas"]}`. Festival opt-in keys are festival ids without the year, so please keep `Festival.id = <key>_<year>`. The bot upserts the returned Customer itself.
- 24 Oct · C → B · The bot calls `decide()` and sends the card itself. Please don't call `deliver()` inside `decide()` for bot triggers, or users get two cards. `/stop` sets `customers.opted_out`; `/pause` sets `customers.paused_until`, and the pre-gate should read both.
- 24 Oct · C → Main · `deliver` and `build_application` are now real. Optional: call `await app.bot.app.set_commands(tg)` after `tg.initialize()` in `main._start_bot` to fill the prod bot's "/" menu.

## 8. Manual setup the user must do (not code)
- [ ] BotFather:
  - create the **Offer bot**;
  - create **10 customer bots** (names/avatars by persona);
  - for the Offer bot, run `/setprivacy` → Disable, so it can see `/lab` commands in the group.
- [ ] Create the Telegram group **"Customer Lab"**, add all 11 bots, and get `LAB_GROUP_CHAT_ID`.
- [ ] Create a private **shadow channel**, add the Offer bot as admin, and get `SHADOW_CHANNEL_ID`.
- [ ] Find your own Telegram user ID (for `ADMIN_TELEGRAM_IDS`).
- [ ] Create the Groq API key.
- [ ] Accounts: GitHub repo, Neon (DB URL), Render (web service), Vercel (frontend), cron-job.org (ping `/health` every 10 min).
- [ ] Put all values in `.env` locally and in the Render/Vercel env settings. **Never commit them.**
- [ ] Share the Offer bot link with classmates on day 1.
- 24 Oct · Main → B, C · **Shared storage helpers on main.** Merge main into your branch to get them.
  - `app.decision_store.save(decision)` is the only way to write a Decision. The harness calls it; dry runs are skipped automatically.
  - Also there: `get(id)`, `set_outcome(id, outcome, at, revenue)` (C uses it for button clicks), `query(...)`, and `spent_on(day)` (₹ sent today, for budget pacing).
  - `app.runtime.killswitch_on()` is the kill switch. The harness pre-gate must return BLOCKED when it is on.
  - Don't write `DecisionRow` or `SettingRow` directly.
- 24 Oct · Main → D · **The REST API from `contracts.md §4` is on main** (`backend/app/api/`). Run it locally with `uvicorn app.main:app --app-dir backend` and set `VITE_USE_MOCKS=0` with `VITE_API_URL=http://localhost:8000`.
  - Writes need the `X-Admin-Passcode` header (401 = wrong passcode, 503 = not configured).
  - The SSE feed is `GET /api/decisions/stream`, sending `event: decision` with a DecisionLight; keepalive comments arrive every 20 s.
  - Lists page with `next`: an ISO timestamp for decisions, a customer id for customers. Pass it back as `cursor`.
  - Extras beyond the contract: `/api/meta` also returns `bot_link` and `ports`; `/api/budget` also returns `today_used_pct`; campaign `totals` also include `over_budget`.
