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

### 2026-10-24 · B · Phase 1: layered rules engine
- **Version/Phase:** v0.2 / Phase 1. Done, waiting for the commit.
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
- **Commits:** _pending_
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
