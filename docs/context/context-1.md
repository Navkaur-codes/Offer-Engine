# context-1.md: Session A, Data & Scoring

**Branch:** `feat/data-scoring`
**Worktree:** its own worktree
**Read first:** `CLAUDE.md`, `docs/claude-progressive.md`, `docs/contracts.md`, `docs/detective.md`, `docs/PLAN.md §2, §4b, §8`

## Mission
Produce **synthetic customer data that behaves like real Indian e-commerce data**, and the **scores** the decision engine runs on:
- RFM, churn risk, uplift, impact estimate, dynamic policy membership;
- realism statistics and experiment statistics for the dashboard.
This session covers the **data realism** judging criterion and supplies the numbers behind the business-relevance criterion.

## Owned paths (only edit these)
`backend/app/data/`, `backend/app/scoring/`, `backend/tests/data/`

## Never touch
`rules/`, `agent/`, `bot/`, `lab/`, `frontend/`, `contracts.py`, `models.py`, `api/`, `main.py`.
If you need a new field, write a contract change request in `docs/sessions.md`.

## Consumes
- `app.contracts`: all models.
- `app.db.get_session`, `app.models` (DB tables), `app.config.now()`.

## Produces (signatures in `contracts.md §3`)
- `data.seed.run()`
- `data.festivals.FESTIVALS`
- `data.onboarding.create_profile_from_answers()`
- `scoring.profile.build_profile()`, `scoring.profile.assign_policy()`
- `scoring.uplift.predict()`, `scoring.impact.estimate()`
- `scoring.realism.compute()`, `scoring.experiments.compute()`

---

## Phase 1 (v0.2): Personas, generator, seed
**Tasks:**
1. `data/personas.py`: the 9 personas from `contracts.Persona`. Each one has:
   - visit rate and order rate;
   - AOV lognormal(μ, σ) per category, with category weights;
   - discount usage, return propensity, churn hazard;
   - response-type mix (e.g. deal_hunter: 50% persuadable, 30% sure_thing, 15% lost_cause, 5% sleeping_dog).
2. `data/catalog.py`: 10 categories with **margin**, price bands, return rate and shipping cost. Plus about 120 products with realistic Indian names and ₹ prices.
3. `data/festivals.py`: the `FESTIVALS` list for Oct 2025 – Jan 2027, covering Navratri, Dussehra, Karwa Chauth, Dhanteras, Diwali/Bandi Chhor, Bhai Dooj, Gurpurab, Black Friday, Christmas, wedding season, Lohri, Makar Sankranti and Republic Day. Each entry has phases, hero categories, greeting, `needs_opt_in`, restricted promos, budget, `delivery_days_by_tier`, and the category **lift multipliers** per phase.
   - **Check the 2026 dates against a reliable panchang/calendar source**, and note the source in a comment.
4. `data/generator.py`: a day-by-day simulation over 12 months (seeded; Faker `en_IN`). It covers:
   - Punjab-heavy city mix (about 45% Punjab) with tiers;
   - signup curve and acquisition channels;
   - sessions following the hour-of-day curve (peak 20:00–23:00 IST);
   - the view → cart → checkout → purchase funnel;
   - returns, points earn/expiry, tiers;
   - **festival and payday lifts**;
   - a churn hazard, which gives a decaying retention curve;
   - deliberately messy data: about 3% missing age, some duplicate sessions, a few heavy returners.
5. **Past campaigns:** a simulated offer history across about 6 campaigns, including **Diwali 2025**, with a random 10% control group. Outcomes follow each customer's hidden `response_type`. This is the uplift model's training data.
6. `data/seed.py` with CLI `python -m app.data.seed --customers 5000 --seed 42`. It writes customers, products, events, orders, offers_sent and redemptions, and runs in under 2 minutes.

**Done when:**
- The seed runs from scratch.
- `tests/data/test_generator_stats.py` passes these target ranges:
  - Pareto top-20% share between 0.65 and 0.80;
  - cart abandonment 0.65–0.75;
  - view→purchase about 2–4%;
  - fashion return rate 0.2–0.3;
  - Diwali-week revenue at least 1.8× a normal week;
  - evening share of sessions at least 35%.

## Phase 2 (v0.3): Profiles, RFM, churn, policies
**Tasks:**
1. `scoring/rfm.py`: quintiles mapped to named segments (Champions, Loyal, Potential, At Risk, Hibernating, New, Lost).
2. `scoring/churn.py`: logistic regression on recency, the trend in purchase frequency, session decline and return rate. Labels come from the simulation (no purchase in the next 60 days). The model is saved as `scoring/models/churn.joblib`; report the AUC.
3. `scoring/profile.py`:
   - `build_profile()` assembles `CustomerProfile` from DB rows and must take under 50 ms.
   - `assign_policy()` maps the profile to a policy using the thresholds in PLAN §4. The thresholds are read from a config dict (this session owns them), not scattered in code.
   - Real-time events (from `/simulate`) must update the profile instantly. For example, 60 days of inactivity must flip the policy to `at_risk`.
4. `data/onboarding.py`: `create_profile_from_answers()` turns a classmate's 3 tap answers into a persona plus about 6 months of generated history that matches them.

**Done when:**
- Unit tests cover each policy's assignment.
- A simulated purchase changes `recency_days` to 0.
- An inactivity simulation flips the policy.

## Phase 3 (v0.4): Uplift, impact, realism and experiment stats
**PRIORITY 1 (found live at GATE-2, 25 Oct).**
- **Problem:** real customers currently have prior uplifts of about 0.03–0.04 and impact is still the stub. The engine (correctly, given those numbers) sends **no offer to almost anyone**.
- **Do first:** `scoring/uplift.py` and `scoring/impact.py`, so the `uplift_predict` / `impact_estimate` ports turn real. Commit them as their own checkpoint.
- **Targets on a 500-customer scratch seed:**
  - persuadables get positive expected profit for at least one offer type;
  - sure-things and sleeping dogs stay ≤ 0;
  - the overall NO_OFFER share for customer-initiated triggers is roughly 30–40%.
- **Report** the share per policy in progress.md.

**Tasks:**
1. `scoring/uplift.py`: a T-learner (two `GradientBoostingClassifier` models, treated vs. control) per offer-type family, trained on the past campaigns.
   - `predict()` returns `P(buy|offer) − P(buy|no offer)`.
   - Save the Qini curve points for the dashboard.
   - Sanity check: predicted uplift for hidden `sure_thing` customers is about 0, and for `sleeping_dog` it is below 0.
2. `scoring/impact.py`: `estimate()` returns `(cost, incremental_profit)`, where cost = discount × AOV × P(redeem) (or shipping cost, or points liability) and incremental_profit = uplift × AOV × margin − cost.
3. `scoring/realism.py`: `compute()` returns `RealismStats` with a `benchmarks` dict of the target ranges, plus a short note on the source of each benchmark.
4. `scoring/experiments.py`: `compute()` returns `ExperimentStats`:
   - treatment vs. holdout;
   - incremental revenue/profit;
   - **margin saved by not discounting sure-things**, i.e. the counterfactual cost of a blanket offer;
   - uplift by policy, ROI by offer type, festival vs. baseline.
   - Data comes from the past campaigns, real decisions and outcomes.

**Done when:**
- The Qini curve beats random.
- The impact estimates rank persuadables above sure-things.
- Stats come back as JSON in under 1 second (cached).

## Phase 4 (v1.0): Tuning and hardening
- Tune parameters until every benchmark sits comfortably within range.
- Speed: seed under 2 minutes; profile build under 50 ms.
- Write `docs/data-dictionary.md` (this session may create it). It lists every table and column, the generation logic, and why each distribution was chosen. Judges read this.
- Add edge cases: customers with 0 orders, customers with missing age, a brand-new Telegram user.

## Stub strategy
You depend only on `contracts`, `db`, `models` and `config`, which already exist after Phase 0. Others consume your work through `app.ports`. Keep the signatures exact.

## Tests
```
pytest backend/tests/data -q
```

## Detective traps to watch
- T12: uniform-random data.
- T13: real data.
- T23: invisible ML.
- T17: religion from names. Festival opt-in is a customer *field*, never derived from the name.

## Handoff checklist (end of each phase)
- [ ] Tests green, `ruff` clean, every finished task given to the user as a 📌 COMMIT CHECKPOINT, and the user confirmed it is pushed to `feat/data-scoring`.
- [ ] Function signatures still match `contracts.md §3`.
- [ ] Entry appended to `docs/progress.md`; your row updated in `docs/sessions.md`.
- [ ] Anything Session B, C or D needs to know written in `sessions.md` under "Notes for other sessions".
