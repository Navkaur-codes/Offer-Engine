# progress.md: version → phase → session log

> **Append-only.** Every session adds an entry at the end of its work, using the template at the bottom.
> The main session updates the version/phase status tables at every phase gate.
> Status key: ☐ not started · ◐ in progress · ☑ done · ⛔ blocked

## Version status
| Version | Target | Milestone | Status |
|---|---|---|---|
| v0.1 | Thu 22 Oct | Scaffold + contracts + bot "hello" deployed, link shared | ☑ |
| v0.2 | Fri 23 Oct | `/simulate cart` end-to-end (decision → validator → Telegram → log) | ◐ Phase 1 merged (GATE-1, 24 Oct); `/simulate` comes in Phase 2 |
| v0.3 | Sat 24 Oct | Dashboard live on the real API (Overview, Decisions, Rules) | ☐ |
| v0.4 | Sun 25 Oct | Uplift + holdout + Customer Lab + Experiments + Playground | ☐ |
| v1.0 | Mon 26 Oct 18:00 | Feature freeze, classmate test round done, README done | ☐ |
| Submit | Tue 27 Oct ≤ 10:00 | Repo + bot username submitted | ☐ |

## Phase status per session
| Session | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| Main (Step 0 + gates + API + deploy) | ☑ Step 0 · ☑ GATE-1 | ◐ MAIN-API | ☐ | ☐ |
| A: Data & Scoring | ☑ `8b2e903` | ◐ | ☐ | ☐ |
| B: Decision Core | ☑ `0202dd8` | ◐ | ☐ | ☐ |
| C: Telegram + Lab | ☑ `1e5e102` | ◐ | ☐ | ☐ |
| D: Dashboard | ☑ `e5d9116` | ◐ | ☐ | ☐ |

## claude-progressive.md history
| Version/Phase | Written | Summary of temporary rules |
|---|---|---|
| v0.1 / Phase 0 | 22 Oct | Scaffold only; contracts may change until the gate |
| v0.2 / Phase 1 | 22 Oct | Contracts v1 frozen; everything through ports/stubs; never poll with the prod token; shared venv; no real Groq calls |
| v0.3 / Phase 2 | 24 Oct | Compressed schedule; real modules replace stubs as they merge; Neon seeded small (≈1,500 customers); still no real Groq calls |

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
- **Commits:** `8b2e903` (merged into main as `948bcb1` at GATE-1)
- **Tests:** `python -m pytest tests -q` (backend) → 54 passed (35 in `tests/data`, 2 seeds) · `ruff check .` clean
- **Open issues / risks:** Lohri 2027 has conflicting sources (13 vs 14 Jan); re-check in January. Seeding Neon over the network will be slower than SQLite; seed locally or with fewer customers if it is slow.
- **Contract change requests:** none
- **Next:** Phase 2: `scoring/rfm.py`, `scoring/churn.py`, `scoring/profile.py` (`build_profile` under 50 ms, `assign_policy`), `data/onboarding.py`.

### 2026-10-24 · B · Phase 1: layered rules engine
- **Version/Phase:** v0.2 / Phase 1. Done.
- **Did:**
  - `rules/rule_types.py`: one class for each of the 11 RuleTypes. Each has `applies` / `constrain` / `check` / `describe`. Rule conditions use `policy`, `persona`, `customer_id`, `festival` (`"*"`, or an id prefix such as `diwali`), `phase`, `city_tier` and `payday`.
  - `rules/seed_rules.py`: 35 seed rules.
    - 8 Global: margin guard, caps, 3 per 7 days / 48 h, quiet hours, daily budget, one coupon, no discount within 48 h of a purchase, message.
    - 7 Festival: budget pool, zero-cost teaser, hero-only build-up, last-minute cap, 5% Dhanteras/Diwali peak cap, no post-festival discount for buyers, restricted promos.
    - 17 Persona rules covering all 9 policies.
    - 3 Individual: "Not for me" suppressions, fraud block, tighter cap.
  - `rules/engine.py`:
    - `effective_policy()` does the tighten-only merge: a looser lower-layer value is ignored, logged as a warning, and noted in the summary.
    - `allowed_offers()` / `screen_offers()` return the narrowed ranges, `rule_notes`, a conservative cost/profit estimate, and the rejected offers with their reasons.
    - `evaluate()` is the one validator. With `offer_id=None` it acts as the pre-gate. It adds a built-in `CATALOGUE` check, and `adjusted_params` suggests a clamped, compliant version.
  - Budget pacing: when `pacing_factor` < 1, the % and ₹ caps shrink proportionally. Candidate notes and the policy summary say so.
  - `rules/describe.py`: the `describe_rule` port. The `effective_policy`, `allowed_offers`, `evaluate` and `describe_rule` ports now resolve to **real**.
- **5 describe() examples:**
  1. Deal hunters can get at most 10% off, only on baskets above ₹999.
  2. Cart abandoners move up a ladder: cart reminders or free shipping once the cart is 30 min old, then up to 5% off once the cart is 24 h old.
  3. Discounts never go above the category margin minus 5 points (beauty up to 45%, grocery up to 7%).
  4. During the last-minute days of Dhanteras or Diwali, customers can get at most 5% off and ₹100 off.
  5. At-risk customers can only get % off, bundles, free shipping, bonus points or cart reminders, and only when the offer lifts their chance to buy by more than 5 points.
- **Files:** `backend/app/rules/{rule_types,seed_rules,engine,describe}.py`, `backend/tests/core/{helpers,test_rule_types,test_engine,test_property}.py`
- **Commits:** `0202dd8` (merged into main at GATE-1)
- **Tests:** `python -m pytest tests/core -q` (from `backend/`) → 30 passed, about 70 s. `ruff check .` is clean.
  - The property test runs 10,000 random decisions. Every approved one is re-checked against a hand-written oracle of the hard limits.
  - A second property checks that any params inside the `allowed_offers` ranges always pass `evaluate`.
  - Spot check that the oracle has teeth: dropping G_QUIET, G_MARGIN, G_BUDGET, P_DEAL_CAP, P_VIP_PERKS or P_CART_LADDER from the rule set gets caught.
- **Open issues / risks:**
  - `tests/api/test_ports.py::test_evaluate_flags_over_limit_discount` (main-owned) now fails on this branch. It expects a deal-hunter `{"pct": 10}` to pass, but the real engine requires `min_basket ≥ 999` (a missing `min_basket` counts as 0). Main should change that case to `{"pct": 10, "min_basket": 999}` at merge.
  - Rules come from the `rules` table and fall back to `SEED_RULES` when it's empty. `seed_rules.ensure_seeded()` inserts any missing seed rows; Main or A's seed CLI should call it. The catalogue comes from the `offers` table, with `stubs.CATALOGUE` as the fallback.
  - Offer param names the engine understands: `pct`, `amount` (flat ₹), `min_basket`, `multiplier`, `category`. A's catalogue should use them.
  - "Once per lifetime" (new-user welcome) and "one try, then stop for 90 days" (dormant) are approximated with gap rules, because the profile has no per-offer history.
- **Contract change requests:** none. `evaluate`, `effective_policy` and `allowed_offers` only gained optional keyword-only `rules=` / `catalogue=` arguments, so the contract signatures are unchanged.
- **Next (Phase 2):** `agent/context.py` (pacing factor from the G_BUDGET `daily_cap`), the harness pre-gate via `evaluate(offer_id=None)`, `MockLLM`, the fallback, and the explainer.

### 2026-10-24 · Session C · Phase 1: onboarding, offer cards, customer commands
- **Version/Phase:** v0.2 / Phase 1. Done, tests green; phone check on the dev bot pending.
- **Did:**
  - `bot/app.py`: factory (`build_application()` kept), handler registration, `/` command menu, error handler that logs type + update id only and replies with friendly copy.
  - `bot/onboarding.py`: `/start` with inline buttons only: consent (synthetic demo) → categories (multi-select) → frequency → deal vs quality → optional festival greetings (opt-in) → `create_profile_from_answers` → upsert customer → `decide(trigger="welcome")` → card.
  - `bot/render.py`: Decision → Telegram HTML card (bold headline, 2 personal lines, `🎟 value · till DD Mon`, coupon in `<code>`, muted footer) + buttons ✅ Claim · ⏰ Remind me tonight · 🙅 Not for me · ❓ Why this?; NO_OFFER / BLOCKED / HELD_OUT (never reveals holdout) / DRY_RUN variants; ₹ with Indian grouping; all text HTML-escaped.
  - `/profile` (plain words, no hidden response type), `/help`, `/offers`, `/why`, `/pause [days]`, `/resume`, `/stop` (sets `opted_out`). Buttons respond; "Remind me tonight" schedules a 19:00 IST job (in-memory). Free text gets "use buttons/commands" (never sent to an LLM).
  - `bot/sender.py`: `send_decision` (interactive) + `deliver(decision, channel)` port (proactive, SENT only). `bot/store.py`: the bot's DB access.
- **Files:** `backend/app/bot/{app,onboarding,render,commands,sender,store}.py`, `backend/tests/bot/{conftest,test_render,test_handlers}.py`, `backend/tests/bot/snapshots/*.html`
- **Commits:** `1e5e102` (merged into main at GATE-1)
- **Tests:** `python -m pytest -q` (backend) → 53 passed · `ruff check .` clean
- **Open issues / risks:**
  - Claim/decline are not recorded yet (Phase 2). Reminder jobs are lost on restart.
  - Festival opt-in keys are ids without the year (`diwali`); A must keep `Festival.id = <key>_<year>`.
  - B's harness must not call `deliver()` itself for bot-originated triggers (double card).
- **Contract change requests:** none
- **Next:** Phase 2: `/simulate …`, recorded button outcomes, `/history`, rate limit.

### 2026-10-24 · Session D · Phase 1: Signal theme, app shell, ⌘K, mocks (recorded by Main at GATE-1)
- **Version/Phase:** v0.2 / Phase 1. Done. D's own progress entry was not in its branch, so Main recorded it here.
- **Did:**
  - Vite + React + TS + Tailwind v4 + shadcn scaffold in `frontend/`.
  - Signal tokens in light and dark mode; Geist / Geist Mono.
  - Dark sidebar; top bar with kill switch, budget meter, "Upcoming moments" chip, bot QR and passcode.
  - ⌘K palette; typed `api.ts` with mocks.
  - Shared components (Kpi, PipelineLens, DataTable, ExplanationCard, RuleCheckList, badges, Money, EmptyState, WhyThisPage).
  - Early Overview and Decisions pages.
- **Commits:** `e5d9116` (merged as `62a4065`)
- **Tests:** `npm run lint` ✓ · `npm run build` ✓. Main bundle is 615 kB (size warning; code-split in Phase 4).
- **Open issues:** the Lighthouse accessibility score is not measured yet.

### 2026-10-24 · Main · GATE-1
- **Merged:**
  - A `8b2e903` → `948bcb1`
  - B `0202dd8` → `90670b6`
  - C `1e5e102` → `9bd7391`
  - D `e5d9116` → `62a4065`
- **Conflicts:** only `docs/progress.md` and `docs/sessions.md`, resolved with every entry kept.
- **Fixes on main:**
  - `tests/api/test_ports.py` updated for the real deal-hunter rule (`min_basket ≥ 999`), as B requested.
  - New port `set_bot_commands`; `main._start_bot` now fills the production bot's "/" menu after setting the webhook, as C requested.
- **Tests:** backend 118 passed · ruff clean · frontend lint + build ✓
- **Smoke (scratch SQLite):** seed of 500 customers in 7 s · real `effective_policy` / `evaluate` · stub `decide` gives SENT / NO_OFFER / BLOCKED · app boots with 8/21 real ports.
- **Next:**
  - push main, so Render redeploys;
  - seed Neon with about 1,500 customers;
  - live check;
  - fast-forward the 4 worktrees;
  - send A2–D2.

### 2026-10-24 · B · Phase 2: harness, fallback, MockLLM, explainer
- **Version/Phase:** v0.3 / Phase 2. Done, waiting for the commit.
- **Did:**
  - `agent/context.py`: `get_context(now)` covers:
    - quiet hours, taken from the G_QUIET rule;
    - the payday window (1st–5th);
    - the active festival and phase (nearest date wins when phases overlap), days to the festival, hero categories, the greeting, and the delivery cutoff (slowest tier);
    - budget left today (the G_BUDGET `daily_cap` minus `decision_store.spent_on(today)`), and the festival pool (`spent_on` summed over the festival window).
    - The pacing factor is 1.0 up to 80% of the budget used, then falls linearly to 0.5 at 100%.
  - `agent/harness.py`: `decide()` runs the exact pipeline.
    1. Pre-gate: kill switch (`runtime.killswitch_on()`), `/stop`, `/pause`, then `evaluate(offer_id=None)`. Quiet hours queue the decision until 09:00 and re-check the rules at that time. Exclusions give NO_OFFER; frequency, stacking and budget give BLOCKED.
    2. `screen_offers` builds the candidates.
    3. Holdout customers get HELD_OUT: the fallback's choice is logged and nothing is sent, with no LLM call.
    4. Agent → `evaluate` → one retry with the violations sent back → fallback. A timeout, 429 or invalid JSON goes straight to the fallback.
    5. Coupon `<TYPE><NAME3><4>` and expiry (+2 days at 23:59, clamped to the festival delivery cutoff during build-up and last-minute).
    6. Every decision is saved through `decision_store.save()` (Main's shared writer), including blocked, no-offer and held-out ones, with its `explain()` output. After Main's 66b3d3a merge I switched my own storage and kill-switch code to these helpers.
    - `dry_run` persists nothing and creates no coupon. It **never** calls `deliver()`.
  - `agent/llm.py`: the `LLMClient` protocol and `MockLLM` with these behaviours: good, no_offer, over_limit, fix_on_retry, invalid_json, timeout, rate_limited, injected.
  - `agent/prompts.py`: the system prompt from PLAN §3. Customer text is wrapped in `<customer_text>`.
  - `agent/fallback.py`: picks the best-profit candidate at its cheapest point (or NO_OFFER), with a template per offer type. The festival greeting is used only if the customer opted in.
  - `agent/explainer.py`: deterministic. "Rejected" groups the offers screened out by the same rule.
  - `rules/offers.py`: a default catalogue of 10 offers plus `ensure_offers_seeded()`.
  - **Rule change you approved:** G_POST_PURCHASE now blocks *all* proactive offers for 48 h after a purchase. It used to block discounts only. This changes 0202dd8, and it makes the GATE-2 smoke step "purchase → cart → NO_OFFER" pass.
- **3 example explanations (for C and D):**
  1. **Sent: Free shipping (exp. 26 Oct)**
     - Why customer: "Trigger cart abandoned: Cart abandoners policy; cart ₹1,450 open (Cotton Kurta); last order 12 days ago; churn risk 0.42; uplift 0.18 for free shipping."
     - Rules: "14 passed · 0 violations · policy Cart abandoners (5426a9)"
     - Telegram: "Why you got this: your Cotton Kurta is still in your cart, so free shipping is the smallest nudge that helps. 14 rules checked ✓"
  2. **Sent: 5% off ethnic wear (exp. 26 Oct)**, decided by "Rules fallback — the agent's offer was rejected twice (CATALOGUE: pct=50 is above the catalogue maximum 30)". This is the over-limit mock.
  3. **No offer for Arjun: no allowed offer is expected to pay for itself** (VIP, sure thing, margin protected). Rejected: "Cart reminder: VIP customers can only get early access, bonus points, free shipping, free express delivery or points reminders."
- **Files:**
  - `backend/app/agent/{context,harness,llm,prompts,fallback,explainer}.py`
  - `backend/app/rules/offers.py`
  - `backend/app/rules/{seed_rules,rule_types}.py` (post-purchase rule and its wording)
  - `backend/tests/core/{test_harness,test_rule_types,test_property}.py`
- **Commits:** `0302b17` feat(agent): decision harness with pre-gate, holdout, retry and rules fallback; deterministic explainer
- **Tests:**
  - `python -m pytest tests/core -q` → 53 passed. `ruff check .` is clean.
  - Every "Done when" case has a test: over-limit → retry → compliant fallback; timeout and invalid JSON → fallback; kill switch → BLOCKED; quiet hours → QUEUED; holdout → HELD_OUT (logged, not sent); purchase < 48 h → NO_OFFER with the reason.
  - Further tests: dry_run, consent, frequency cap, sleeping dog, an injected name, and a check that `deliver` is never called.
- **Open issues / risks:**
  - Two tests outside my folder fail now that `decide` is real (details in `sessions.md §7`):
    - `tests/api/test_ports.py::test_decide_covers_sent_no_offer_and_blocked` assumes the stub rule "manual → BLOCKED".
    - `tests/bot/test_handlers.py::test_offers_and_why_after_welcome` uses the real clock, so after 21:00 IST the welcome is QUEUED.
  - **Demo risk:** quiet hours (non-negotiable §10) also queue replies to customer-initiated `/simulate` and `/start` between 21:00 and 09:00. Judges testing at night will see "Queued for 09:00". Needs a decision; see `sessions.md`.
  - `build_profile` is still the stub. A's real profile must fill `recency_days`, `offers_7d`, `last_offer_at` and `active_coupon` from orders and decisions, or the post-purchase, frequency and stacking rules can't fire.
- **Next (Phase 3):** `groq_client.py` (Groq behind `LLMClient`), read-only tools, the 6-step loop, and message number/expiry/greeting checks. This waits for the LLM budget-guard decision.
