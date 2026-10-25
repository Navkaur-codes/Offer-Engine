# sessions.md: overview of all sessions and integration health

> This is the control tower. Each session updates **only its own row** and adds notes. The **main session** runs the gate checklist and health log, and decides on contract change requests.

## 1. Session board
| Session | Branch / worktree | Context file | Current phase | Status | Contract ver. | Blockers | Last update |
|---|---|---|---|---|---|---|---|
| Main / Integrator | `main` · `D:\hackathon-2` | `CLAUDE.md`, `docs/PLAN.md` | GATE-3 passed → Phase 4 (README, demo script, final deploys) | ☑ GATE-1 ☑ MAIN-API ☑ GATE-2 ☑ GATE-3 | v1.1 (+ CCR-B1, CR-C1) | none | 25 Oct |
| A: Data & Scoring | `feat/data-scoring` · `D:\offer-engine-A` | `docs/context/context-1.md` | Phase 3 done (A3) → Phase 4 next | ☑ P3 `dad6a5a` + realism/experiments (P2 `1646fe0`, P1 `8b2e903`) | v1.1 | Main: reseed Neon after merging A3 | 25 Oct |
| B: Decision Core | `feat/decision-core` · `D:\offer-engine-B` | `docs/context/context-2.md` | Phase 4 done (free-perk override, digest, rule preview, profiling) | ◐ P4 awaiting commit (task 0 `aa0db26`) | v1.1 | none | 25 Oct |
| C: Telegram + Lab | `feat/telegram-lab` · `D:\offer-engine-C` | `docs/context/context-3.md` | Phase 3 done (Customer Lab live in the group: 10 customers, 4 bots, /lab commands); /simulate verified on the real harness → Phase 4 next | ☑ P3 `fe3e883` (P2 `9cfaf33`, `21e43d9`; P1 `1e5e102`) | v1.1 | CR-C1 open; prod needs `ADMIN_TELEGRAM_IDS` + `CUSTOMER_BOT_TOKENS` on Render | 25 Oct |
| D: Dashboard | `feat/dashboard` · `D:\offer-engine-D` | `docs/context/context-4.md` | Phase 3 done (live API by default with v1.1, Rules editor, Customers, Automations tile; Vercel-ready) → Phase 4 next; Lighthouse not yet measured; bundle ~1 MB, code-split in P4 | ☑ P3 `82ada66`, `f0fa291`, `59015a5` (P2 `a9aa536`, `181eb92`, `fc08f23`; P1 `e5d9116`) | v1.1 | none (CR-D1, CR-D2 accepted in v1.1) | 25 Oct |

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
| 25 Oct 18:15 | GATE-3 | `pytest` 279 passed · ruff clean · frontend lint + build ✓ | Render (gpt-oss, `decide_batch`, `llm_budget`) + Vercel https://offer-engine-nu.vercel.app · Neon re-seeded | scratch: 79% would send, 0 validator failures; live agent decisions ✓; Lab ran 6 rounds in the group ✓; dashboard live ✓ | fallback "2×" validator bug fixed by B `13a4cf4`; agent picks "no offer" too often in the Lab → B Phase 4 priority |
| 25 Oct 00:10 | GATE-2 | `pytest` 214 passed · ruff clean · frontend lint + build ✓ | Render redeployed (real pipeline) | scratch smoke ✓ (40 real decisions in 1.1 s; SENT/QUEUED/HELD_OUT/BLOCKED); live onboarding ✓ after the BIGINT fix `7c8d629`; decisions logged in Neon ✓ | every decision is NO_OFFER (uplift prior + stub impact) → Phase 3 priority 1 for A and B |
| 24 Oct 20:01 | GATE-1 | `pytest` 118 passed · ruff clean · frontend lint + build ✓ | pending (push main) | scratch seed of 500 customers in 7 s ✓; real rules: 50% off blocked, 10% + ₹999 allowed ✓; stub decide gives SENT / NO_OFFER / BLOCKED ✓; app boots, 8/21 ports real (+ `set_bot_commands`) | merges `948bcb1` A · `90670b6` B · `9bd7391` C · `62a4065` D; only progress/sessions docs conflicted (resolved, all entries kept); the stub test was updated for the real ₹999 deal-hunter rule |
| 22 Oct 17:38 | GATE-0 | `pytest` 19 passed · ruff clean | Render live: `/health` ok, bot true, 0.8 s | wrong-secret webhook returns 403 ✓; `/start` hello (user) ✓ | all 21 ports are stubs except `build_application` |

## 6. Contract change requests
Format: `ID · date · from session · what change · why · status (open/accepted/rejected) · contract version`
- _none yet_
- CR-D1 · 24 Oct · D · `Kpis.deltas`: use the same keys as the `Kpis` fields (`sent_today`, `claim_rate`, `incremental_revenue`, `budget_used_pct`, `blocked_by_rules`, `margin_saved`), with values as a fractional change vs yesterday (`0.12` = +12%). The API currently sends `{"sent","claim_rate","blocked"}` and it's unclear whether those are absolute or relative. · The KPI strip shows ▲▼ per tile and can't map the current keys without guessing. · open · v1
- CR-D2 · 24 Oct · D · Add `festival: str | None` to `DecisionLight` and a `festival=` filter to `GET /api/decisions`. · context-4 Phase 2 asks for a festival filter on the Decisions log; today only `trigger=festival` exists, which misses festival-phase decisions from other triggers. · open · v1
- CCR-B1 · 25 Oct · B · Add ports `llm_budget_status` → `app.agent.budget.status` and `decide_batch` → `app.agent.harness.decide_batch` · so `/health`, the dashboard meter, campaign dry-runs and the Lab use the budget guard and the top-5 rule through ports · accepted (GATE-3, Main wired ports + /health + campaign dry-run) · v1.1
- CR-C1 · 25 Oct · C · `CustomerBotRow` (`customer_bots`): make `customer_id` the primary key (one row per Lab customer) and keep `username` as a plain indexed column. · With 1–10 bots voicing 10 customers, one bot voices several customers, which the current `username` primary key forbids. A's seed also keeps only customers listed there, so today it deletes the Lab customers' rows (C's `ensure_lab_customers()` rebuilds them before each round). Until then C stores the voice in `customers.attrs["lab_voice"]`. · accepted (GATE-3, model + Postgres migration on main; C/A may now write and keep `customer_bots` rows) · v1.1

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
- 24 Oct · C → A/B · `/simulate` writes real rows for `TG…` customers: `events` (session/view/add_to_cart/purchase/offer_claimed/offer_declined), `orders`, `points_ledger`, and `customers.suppressed = {category: until_iso}` (14 days after "Not for me"). `/simulate inactive N` shifts the customer's events and orders N days back. Triggers + meta: `cart_abandoned {category,item,value,minutes}`, `browse_interest {category,views}`, `inactivity {days}`, `points_expiry {points,expires_on}`, `festival {festival,phase,days_to_festival}`, `payday {day}`. A: please read `suppressed` into `CustomerProfile.suppressed_categories`. B: the bot updates `decisions.outcome` only if the harness has written the row.
- 24 Oct · C → Main · `deliver` and `build_application` are now real. Optional: call `await app.bot.app.set_commands(tg)` after `tg.initialize()` in `main._start_bot` to fill the prod bot's "/" menu.
- 25 Oct · A → Main · With the real `build_profile`, `tests/api/test_ports.py::test_evaluate_flags_over_limit_discount` fails: it asks for stub fixture `C000002`, which isn't in the empty test DB (`KeyError`). That test is about `evaluate`, so when merging A please change its first line to `p = stubs.PROFILES["C000002"]` (and add `from app import stubs`). The other 151 backend tests pass.
- 25 Oct · A → B, C, Main · `scoring.profile.build_profile(customer_id, now)` reads the live DB on every call, with no per-customer cache. It counts only rows with `ts ≤ now`, so time-travel and fresh `/simulate` events show up immediately. It raises `KeyError` for an unknown customer. It takes ~5 ms p50 and ~12 ms p95 on SQLite with 5,000 customers.
- 25 Oct · A → C · `/simulate` should insert `EventRow`s (types from contracts: `purchase` with category, item and value; `add_to_cart`; `session`; `view`). Inserting the event is enough: a `purchase` sets `recency_days=0`, and an `add_to_cart` newer than the last purchase becomes `open_cart` (it includes `"minutes"`). After 30 minutes the policy is `cart_abandoner`. For "inactive", call `build_profile` / `decide` with `now` ≥ 60 days after the last purchase: a customer with ≥2 orders and LTV ≥ ₹2,500 then flips to `at_risk`.
- 25 Oct · A → C · `create_profile_from_answers` writes the customer row and ~180 days of matching history itself (≈250 ms; call it in a thread as you do). `store.save_customer` afterwards only updates it. Re-running /start replaces just the generated history; `/simulate` events are kept. Answers map to personas: weekly+quality → VIP, weekly+balanced → cart abandoner (with a fresh open cart), monthly+balanced → at-risk, occasionally+balanced → window shopper, rarely → new user, deal → deal hunter. Real Telegram users get `is_holdout=False`, so no classmate is silently held out.
- 25 Oct · A → B, D · `profile.rfm` carries extra keys besides `r/f/m/segment`: `orders_total`, `views_90d`, `days_since_active`, `tenure_days`, `spend_365d` and `vip_spend_365d`. `assign_policy` needs them, and the contract has no fields for them. Show them as "key signals" if useful. The policy thresholds live in `scoring.profile.POLICY_THRESHOLDS`. Policy order: high_returner → sleeping_dog → vip → cart_abandoner → dormant → at_risk → new_user → deal_hunter → window_shopper → default.
- 25 Oct · A → B · `profile.uplift` is a transparent prior for now: offer-type prior × (0.4 + price sensitivity) × (1 − P(buys anyway)), always ≥ 0, so `sleeping_dog` can't trigger yet. The T-learner (`scoring.uplift.predict`) replaces it in Phase 3. `churn_risk` comes from the trained logistic model (AUC 0.78).

- 24 Oct · B → Main · `decide` is now real. `tests/api/test_ports.py::test_decide_covers_sent_no_offer_and_blocked` assumes the stub rule "manual → BLOCKED"; the real harness has no such rule, so please update or drop that line.
- 24 Oct · B → C · `tests/bot/test_handlers.py::test_offers_and_why_after_welcome` uses the real clock. Between 21:00 and 09:00 IST the welcome decision is QUEUED (quiet hours), so `/offers` shows none. Pin the time in the test with `config.set_time_override(datetime(2026, 10, 24, 14, 0, tzinfo=IST))`. Also render QUEUED decisions with a "we'll send this at 09:00" card.
- 24 Oct · B → Main · At startup, call `app.rules.offers.ensure_offers_seeded()` next to `seed_rules.ensure_seeded()`; it seeds the 10 default offers into `offers`. QUEUED decisions are stored with status `QUEUED` and the channel already set. A 09:00 scheduler job should deliver them and flip them to SENT (via `decision_store.save`). Because `spent_on` counts SENT only, queued costs reach the budget once they are flipped.
- 24 Oct · B → A · `build_profile` must fill `recency_days` (days since the last purchase), `offers_7d`, `last_offer_at` (from SENT decisions) and `active_coupon` (an unexpired SENT decision with a coupon and outcome pending/claimed). Without them, the post-purchase (now: no offers for 48 h), frequency and one-coupon rules can't fire.
- 24 Oct · B → Main/user · **Decision needed:** quiet hours also queue replies to customer-initiated `/start` and `/simulate` at night, so a judge testing at 22:00 gets "Queued for 09:00". Option: exempt customer-initiated triggers (`welcome`, `lab`, `/simulate` from the user themself) from quiet hours. Unsolicited sends (campaign, festival, inactivity) would stay queued. That relaxes non-negotiable §10, so only Main/the user can decide.

- 24 Oct · B → Main · The harness calls `runtime.quiet_hours_apply` when it exists, and otherwise uses an identical local copy in `agent/harness.quiet_hours_apply`. After GATE-2 merges your helper, the local copy is never used; I'll drop it in B3.
- 25 Oct · A → Main · **Reseed Neon after merging A3a.** With the user's OK, the generator now makes the hidden response type observable (coupon use and "Not for me" declines), and the uplift model was trained on that. Old Neon data still works, but the uplift signal is weaker there.
- 25 Oct · A → B · `uplift_predict` and `impact_estimate` are real now.
  - Paid offers: profit = (uplift − 0.01) × basket × margin − cost, where cost = what's given away × P(buy | offer). Sure-things therefore come out negative.
  - Zero-cost offers: est_cost = 0, profit = max(uplift, 0) × basket × margin, or negative when uplift < −0.01 (a sleeping dog).
  - On a 500-customer seed (customer-initiated `browse_interest`, fallback path), NO_OFFER is 47% with the current "profit > 0" and a projected 20% with "zero-cost at ≥ 0". The 30–40% target falls in between, so please tune it with your rule. Per-policy numbers are in progress.md (A3a).
- 25 Oct · A → B · Predicted uplifts are probabilities over a 7-day window: typical persuadables get +0.02 to +0.05, sure-things about 0. `P_ATRISK_WINBACK`'s `min_uplift: 0.05` therefore blocks about 82% of at-risk customers. Consider 0.02.
- 25 Oct · A → B, D · `profile.rfm` also has `offers_received` and `offers_declined` now (campaign offers plus "Not for me" taps on logged decisions), which help explain sleeping dogs. `scoring.uplift.qini()` returns the Qini points for the Experiments page.
- 25 Oct · A → Main, D · `realism_compute()` and `experiments_compute(start, end)` are real.
  - Both read the live DB and are cached (realism 1 h, experiments 10 min per range).
  - First call: ~1 s on 5,000 customers for realism, less for experiments; afterwards ~0 ms. Optional: call both once at startup to warm the cache.
  - `RealismStats.benchmarks[key] = {"min","max","value","ok","source"}`, covering pareto, cart abandonment, view→purchase, fashion returns, evening sessions and the Diwali week.
  - `ExperimentStats` pools past campaigns (treated vs 10% control) with live decisions (SENT vs HELD_OUT, conversion = a purchase within 7 days).
    - `treatment`/`control` also carry `revenue_per_customer`.
    - `uplift_by_policy` rows: `{policy, n_treated, n_control, treated_conv, control_conv, uplift}`.
    - `roi_by_offer_type` rows: `{type, n, incremental_revenue, cost, incremental_profit, roi}`; `roi` is null for zero-cost.
    - `festival_vs_baseline` rows: `{festival, id, date, revenue_per_day, baseline_per_day, lift}`.
  - Story for the demo, on the 5,000-customer seed: blanket 15% off lost money (ROI −0.07) while flat ₹ off returned 3.1×. ₹1.46 lakh of the ₹2.76 lakh coupon spend went to people who'd have bought anyway (`margin_saved_sure_things`).

- 25 Oct · B → Main/user · **Groq model ids:** this key has no llama models (`llama-3.3-70b-versatile` → 404). Set `GROQ_MODEL_AGENT=openai/gpt-oss-120b` and `GROQ_MODEL_FAST=openai/gpt-oss-20b` in Render and `.env`, or change the defaults in `config.py`. 20 live runs on gpt-oss-120b: 1 call per decision, about 2.3k tokens, about 3 s.
- 25 Oct · B → Main · New B functions that need ports (contract change request CCR-B1 in §6): `app.agent.budget.status() -> dict` for `/health` and the dashboard's LLM budget meter, and `app.agent.harness.decide_batch(items: list[(customer_id, trigger, meta)], *, dry_run, now, agent_top_n=5) -> list[Decision]` for campaign dry-runs and `/lab run` > 5 rounds (top-5 rule, T26).
- 25 Oct · B → D · `budget.status()` returns `{"agent": {"used", "limit", "model"}, "fast": {...}, "mode": "70b"|"8b"|"rules"}`. The mode is still called "70b"/"8b" even on gpt-oss.
- 25 Oct · B → C · Agent messages are now validated for facts: a festival greeting only appears for opted-in customers, every number matches the offer, and the expiry date is real. `evaluate()` without a catalogue now uses the default 10 offers when the `offers` table is empty.

- 25 Oct · B → D · `rule_impact` is real. It returns `{customers_affected, budget_delta, examples, sample_size}`. `examples` are `{customer_id, first_name, before, after}` (your `ImpactLine` already reads `customer_id`). `budget_delta` is the change in worst-case spend headroom over a fixed 500-customer sample (negative = tighter). Consider showing `before → after` of the first example on the rule card.
- 25 Oct · B → Main · `daily_digest` is real: 5 lines, numbers computed in code, gpt-oss-20b rewrite only when every number matches, template otherwise. It charges the fast budget. Profiling: fallback `decide` p50 25 ms / p95 39 ms; agent p50 about 2 s.

## 8. Manual setup the user must do (not code)
- [ ] BotFather:
  - create the **Offer bot**;
  - customer bots: **4 created** (BotFather rate limit on 25 Oct). Rename them `Lab Shopper 1–4` with `/setname`; they voice all 10 Lab customers;
  - for the Offer bot, run `/setprivacy` → Disable, so it can see `/lab` commands in the group.
- [ ] Create the Telegram group **"Customer Lab"**, add the 4 Lab Shopper bots + the Offer bot (+ dev bot), then type `/lab here` in it once C3 is live. No chat ID is needed.
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
- 24 Oct · Main → all · **Contracts v1.1:** CR-D1 and CR-D2 are accepted and implemented on main (see contracts.md §6). `CONTRACT_VERSION="v1.1"`.
- 24 Oct · Main → B · **LLM budget guard approved** by the user. context-2 Phase 3 and prompt B3 now cover the single-call agent, `agent/budget.py` (70B → 8B at 80% → rules at 100%), and the top-5 batch rule. Config: `settings.llm_daily_tokens_agent` / `llm_daily_tokens_fast`.
- 24 Oct · Main → B, C · **Two user decisions, now on main:**
  1. **Quiet hours apply to proactive sends only** (CLAUDE.md §2.10).
     - The harness pre-gate calls `runtime.quiet_hours_apply(trigger, trigger_meta)` and queues only when it returns True.
     - C sets `trigger_meta["initiated_by"]="customer"` on `/start` welcome, `/simulate` and buttons. The API's simulate sets `"admin"`. Lab rounds (`trigger="lab"`) are exempt.
  2. **The shadow channel is removed, and the Lab group is auto-detected.** C implements `/lab here` (admin-only) with `runtime.set_lab_group(chat_id, title)`; everything reads the group from `runtime.lab_group_chat_id()`. `SHADOW_CHANNEL_ID` is gone from config.
- 25 Oct · Main → C · **The Lab uses 4 bots for 10 customers.** BotFather rate-limited the user at 4 bots.
  - Design for 1–10 bots: 10 fixed Lab customers `C900001`–`C900010`, assigned to bots round-robin.
  - Every post starts with `👤 Name · persona`, and the Offer bot addresses the customer by name.
  - `CUSTOMER_BOT_TOKENS` minimal format is `[{"token":"..."}]`; extra keys are ignored. See context-3 Phase 3.
- 25 Oct · C → A/D/Main · Customer Lab customers are `C900001`–`C900010` with `is_lab_bot=True`, `is_holdout=False`; their history rows use ids `E<cid>-L…` / `O<cid>-L…`. A: a re-seed deletes them (CR-C1); C rebuilds them before every round, so no action is needed unless CR-C1 is accepted. D: Lab decisions have `trigger="lab"`, and `customers.attrs.lab_voice` holds the Lab Shopper username. Main: production `/lab` needs `ADMIN_TELEGRAM_IDS` and `CUSTOMER_BOT_TOKENS` on Render; the port `run_rounds(n)` is now real (sync, posts into `runtime.lab_group_chat_id()`).
- 25 Oct · Main → all · **GATE-3 passed.** Dashboard: https://offer-engine-nu.vercel.app. Groq models are `openai/gpt-oss-120b` / `openai/gpt-oss-20b`. New ports: `ports.decide_batch(items, dry_run=, now=, agent_top_n=5)` and `ports.llm_budget_status()` (also in `/health` as `llm_budget`).
- 25 Oct · Main → A, C · **CR-C1 is on main:** `customer_bots` is keyed by `customer_id`. C: write one `CustomerBotRow(customer_id, username, persona)` per Lab customer when you assign voices (you can keep `attrs.lab_voice` too). A: the seed already keeps customers listed in `customer_bots`, but it still deletes their `C…` events/orders; please also skip `is_lab_bot` customers and their rows, so a re-seed never wipes the Lab.
- 25 Oct · Main → B · **Live Lab finding:** in 6 Lab rounds the agent chose "no offer is worth its cost" for a cart abandoner, a new user and a deal hunter. The rules fallback would have sent a zero-cost perk. Make the agent prefer the best zero-cost allowed offer when one exists (profit ≥ 0), and only pick no-offer when nothing allowed pays for itself. Phase 4 task 0.
