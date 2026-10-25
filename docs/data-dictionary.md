# Data dictionary: the synthetic world behind the Offer Engine

> **Everything here is synthetic** (non-negotiable §2.1). No real customer, no scraped profile, no real phone number. Names come from Faker `en_IN`; behaviour comes from our own day-by-day simulation.
> Owner: Session A (`backend/app/data/`, `backend/app/scoring/`).

**Reproduce it:**

```
python -m app.data.seed --customers 5000 --seed 42
```

The same seed gives the same world. It takes about 40 s on SQLite and writes about 760k rows.

---

## 1. How the world is generated (one screen)

`app/data/generator.py` simulates **1 Oct 2025 → yesterday (IST)**, one day at a time, for every customer at once (vectorised numpy).

1. **Customers are drawn first** (§3): a hidden persona, a hidden response type, a city, a signup date, a churn date, and a personal activity level.
2. **Each day, each active customer opens Poisson(λ) sessions**, where:

   ```
   λ = persona visit rate × personal activity (lognormal, σ 0.85)
       × month seasonality × weekday × payday (1st–5th: ×1.12)
       × festival lift (strongest active festival, scaled by the persona's festival sensitivity)
       × campaign effect (only while holding a past-campaign offer, by hidden response type)
       × 0.03 once churned × 1.6 in the first 14 days after signup
   ```
3. **Each session runs a funnel:**
   - session → views (1 + Poisson(1.8)) → add_to_cart → checkout_started → purchase.
   - The step probabilities come from the persona, lifted by festivals, payday and campaigns.
   - The category is drawn from the customer's own affinity (a Dirichlet around the persona's weights) × festival hero-category lift × season (winter wear peaks Dec–Jan).
4. **Each purchase gets a value and a product:**
   - The order value is **lognormal per category**, matched to a real catalogue product, plus a quantity (1–4).
   - A coupon is used with the persona's discount propensity.
   - The return probability depends on the category, the persona and COD (COD returns ×1.25).
5. **Points, tiers and campaigns follow the orders:**
   - Points: 1 per ₹100 on kept orders, expiring after 180 days.
   - Tier: Bronze / Silver / Gold / Platinum by spend in the last 365 days.
   - **Past campaigns** run inside the same loop, with a random **10% control** group (§6).
6. **Messy on purpose:**
   - ~3% missing age and ~4% missing gender;
   - ~0.8% duplicate session beacons (same session id, 0–2 s apart);
   - ~1% extra heavy returners outside the high-returner persona;
   - late-night sessions that finish after midnight.

Because it is one behaviour model, the funnel, seasonality, retention and campaign outcomes are **consistent with each other**. They aren't independently randomised columns (detective T12).

---

## 2. Realism benchmarks (checked by `tests/data/test_generator_stats.py` and shown live on the Realism page)

| Benchmark | Target | Seed 42 (5,000) | Worst of 10 worlds* | Why this target |
|---|---|---|---|---|
| Revenue share of the top 20% of buyers | 0.65–0.80 | 0.759 | 0.788 | Pareto 80/20; repeat-buyer concentration in Indian e-commerce |
| Cart abandonment | 0.65–0.75 | 0.700 | 0.684 | Baymard Institute average ≈ 70% |
| Product view → purchase | 2–4% | 3.1% | 3.3% | Typical e-commerce conversion |
| Fashion return rate | 0.20–0.30 | 0.245 | 0.271 | Indian fashion e-commerce ≈ 25% |
| Diwali week ÷ median week revenue | ≥ 1.8 (shown as 1.8–4.0) | 3.09 | 2.28 | Festive-week GMV ≈ 2–3× (RedSeer festive reports) |
| Sessions 19:00–23:59 IST | ≥ 35% | 41.7% | 41.5% | Indian mobile shopping peaks late evening |

\* Seeds 42, 7, 1, 3 and 11, at 1,500 and 5,000 customers. Every benchmark stayed inside its range in all ten worlds. The Realism page recomputes these from whatever is seeded, with the source of each.

**Known trade-off: Pareto runs on the high side (0.76–0.79).**
- Narrowing the per-customer activity spread (σ 0.85 → 0.7 or 0.6) pulls it to about 0.75.
- But the uplift model was trained at σ 0.85, and in that world it loses most of its persuadable signal. Persuadables' expected profit fell to about ₹0, against +₹3 to +₹7 at 0.85.
- We kept σ = 0.85, so the data and the model stay consistent. Strong revenue concentration is also normal for Indian marketplaces, where a small base of repeat buyers dominates GMV.

Also true by construction:
- AOV ranks electronics > jewellery > … > beauty ≈ grocery.
- Returns rank fashion > ethnic wear > winter wear > electronics > grocery.
- Monthly cohorts show a decaying repeat-purchase curve.
- Dhanteras, Diwali, Black Friday and Karwa Chauth days run 2–4× a normal day.

---

## 3. Customers: personas and hidden truth

Nine **personas** (`app/data/personas.py`). The persona is ground truth for the generator. Scoring never reads it to make decisions: policies are re-derived from behaviour on every event.

| Persona | Share | Sessions/day | Cart → purchase | AOV × | Coupon use | Returns × | Hidden response mix (P / S / L / SD) |
|---|---|---|---|---|---|---|---|
| loyal_vip | 6% | 0.24 | 0.47 | 1.45 | 10% | 0.7 | 15 / 70 / 5 / 10 |
| deal_hunter | 16% | 0.17 | 0.28 | 0.80 | 70% | 1.0 | 50 / 30 / 15 / 5 |
| at_risk_regular | 10% | 0.16 | 0.34 | 1.10 | 25% | 0.9 | 55 / 10 / 25 / 10 |
| new_user | 10% | 0.15 | 0.24 | 0.90 | 45% | 1.0 | 45 / 20 / 25 / 10 |
| dormant | 12% | 0.11 | 0.22 | 0.90 | 30% | 1.0 | 25 / 5 / 55 / 15 |
| window_shopper | 16% | 0.20 | 0.19 | 0.85 | 30% | 1.0 | 30 / 10 / 45 / 15 |
| cart_abandoner | 12% | 0.15 | 0.14 | 1.00 | 35% | 1.0 | 60 / 10 / 20 / 10 |
| festive_gifter | 12% | 0.07 (×2.4 in festivals) | 0.34 | 1.50 | 30% | 0.8 | 35 / 40 / 15 / 10 |
| high_returner | 6% | 0.17 | 0.32 | 1.10 | 35% | 3.0 | 25 / 30 / 20 / 25 |

P = persuadable, S = sure-thing, L = lost cause, SD = sleeping dog.

**Hidden response type**, the ground truth the uplift model has to discover:
- **persuadable** buys mainly when there is a deal: coupon use ×1.7, and an offer lifts visits by up to +70% and conversion by up to +120%.
- **sure_thing** buys anyway, at full price: conversion ×1.35, coupon use ×0.3, and an offer changes nothing (so it's pure margin loss).
- **lost_cause** barely shops, offer or not.
- **sleeping_dog** is put off by marketing: an offer halves activity, 8% go quiet for good, and 45% tap "Not for me" (vs 2–4% for the others).

These traces are why the T-learner can find them. Without them, no model could (we tested T-, X- and transformed-outcome learners).

**Churn:**
- Most personas have a daily hazard (0.04%–0.2%), which gives a decaying retention curve.
- `at_risk_regular` customers go quiet 45–110 days before the end of the simulation.
- `dormant` customers go quiet within 20–150 days of their activity starting, and at least 150 days before the end.
- Churned customers keep 3% of their activity, so the odd stray visit stays realistic.

**Signups:** 55% existed before the simulated year (signed up 1–730 days earlier). The rest join along a growing curve with festival bumps. `new_user`s join in the last 60 days.

**Location and payment:**
- About 45% Punjab (Ludhiana, Amritsar, Jalandhar, Patiala, Mohali and 8 tier-3 towns); the rest Delhi, Chandigarh, Mumbai, Bengaluru, Gurugram, Jaipur, Lucknow and others.
- Tier 1/2/3 drives the payment mix: UPI 55–62%, COD 13–37% (higher in tier 3), card 8–25%.

**Festival opt-ins** come from a random 60% of customers choosing festival keys, **never from their name** (detective T17).

---

## 4. Tables written by Session A

Money is whole rupees (int). Timestamps are IST: `timestamptz` on Postgres, IST wall time on SQLite. Synthetic customer ids are `C000001…`; real Telegram users are `TG<id>`; Lab customers are `C9000xx`.

### `customers` (one row per customer)

| Column | Type | How it's made / meaning |
|---|---|---|
| `id` | str PK | `C000001…` (synthetic), `TG<telegram id>` (onboarded classmate), `C9000xx` (Customer Lab) |
| `first_name` | str | Faker `en_IN`, gender-matched; Telegram first name for real users |
| `age` | int, null | Normal(persona mean, sd), clipped 18–72; **~3% null on purpose** |
| `gender` | str, null | F/M (52/48); ~4% null |
| `city`, `city_tier` | str, int | Weighted city list (§3); tier 1/2/3 |
| `signup_date` | date | §3 signup curve |
| `channel` | str | organic 30%, google_ads 22%, instagram 20%, whatsapp_referral 13%, affiliate 8%, youtube 7% (`telegram`/`lab` for real/Lab users) |
| `device` | str | android 72%, web 18%, ios 10% |
| `preferred_payment` | str | upi / cod / card by tier |
| `persona` | str | Hidden persona (§3) |
| `response_type` | str | **Hidden** ground truth: persuadable / sure_thing / lost_cause / sleeping_dog. Never shown to the agent |
| `telegram_chat_id` | BIGINT, null | Real users only |
| `is_lab_bot` | bool | Customer Lab customers; the seed never touches them or their history |
| `opt_in_festivals` | JSON list | Festival **keys** (`diwali`, `gurpurab`, …), year-free |
| `opted_out`, `paused_until` | bool, ts | Consent (`/stop`, `/pause`); never set by the generator |
| `is_holdout` | bool | Random 10% control for synthetic customers; always false for real Telegram users |
| `points_balance` | int | Unexpired points at the end of the simulation |
| `tier` | str | Bronze < ₹10k ≤ Silver < ₹30k ≤ Gold < ₹75k ≤ Platinum (365-day kept spend) |
| `suppressed` | JSON | `{category: until}` from "Not for me" (written by the bot) |
| `attrs` | JSON | `state`, `churn_date` (hidden), `heavy_returner`; onboarding answers for real users |

### `products` (120 rows): `id` (`P001…`), `name`, `category`, `price`, `margin`
- 12 products per category with Indian market names and realistic ₹ prices, spread across the category's price band so the lognormal order values always find a match.
- Category economics (`app/data/catalog.py`):

| Category | Margin | Median order (₹) | σ | Base return rate | Shipping cost (₹) |
|---|---|---|---|---|---|
| fashion | 50% | 1,100 | 0.55 | 21% | 60 |
| ethnic_wear | 48% | 1,800 | 0.60 | 17% | 70 |
| electronics | 10% | 7,500 | 0.90 | 7% | 120 |
| beauty | 50% | 650 | 0.50 | 5% | 50 |
| home_decor | 40% | 1,300 | 0.60 | 8% | 90 |
| kitchen | 30% | 1,500 | 0.60 | 6% | 90 |
| grocery | 15% | 700 | 0.45 | 2% | 40 |
| jewellery | 25% | 5,500 | 0.90 | 5% | 80 |
| gifting | 35% | 1,200 | 0.55 | 4% | 60 |
| winter_wear | 45% | 1,900 | 0.50 | 14% | 70 |

Margins follow public Indian norms: electronics ~10%, grocery ~15%, fashion and beauty ~50%. They feed the margin guard and every impact estimate.

### `events` (about 760k rows at 5,000 customers): the behaviour log

| Column | Meaning |
|---|---|
| `id` | `E00000001…` in time order. Onboarding and Lab rows use `E<customer>-…` / `E<customer>-L…` |
| `customer_id`, `ts` | Who and when (IST). Session start hours follow a curve peaking 20:00–23:00 |
| `type` | `session`, `view`, `add_to_cart`, `checkout_started`, `purchase`, `return`, `wishlist`, `offer_received`, `offer_claimed`, `offer_declined` |
| `category`, `item`, `value` | Product context; `value` is the price (views) or the order value (cart, checkout, purchase, return) |
| `meta` | `{"sid": n}` links a session's events; `order_id` on purchase/return; `campaign` on offer events |

### `orders` (about 15k rows): `id` (`O0000001…`), `customer_id`, `ts`, `category`, `items` (1–4), `value`, `discount`, `coupon_code`, `payment_method`, `returned`
- `coupon_code` is `SAVE5/10/15` for everyday coupons, or the campaign code (`DIWALI15`, `BF300`, `LOHRISHIP`, `HOLI2X`, `SUMMER10`, `AZADI200`) when the order used a past-campaign offer.
- `returned` is only true when the return happened before the end of the simulation.

### `points_ledger`: `customer_id`, `ts`, `delta`, `reason` (`earn:<order>` / `expiry`), `expires_on`
Earn rows on kept orders (×2 during the Holi double-points campaign), and expiry rows after 180 days. `build_profile` replays the ledger up to `now`, so points about to expire drive the `points_expiry` trigger.

### `campaign_history` (about 7.4k rows): the uplift model's training data
`campaign_id`, `customer_id`, `sent_at`, `offer_type`, `params`, `is_control`, `converted` (bought within the campaign window), `revenue`.

### `festivals` (26 rows): `id` (`diwali_2026`), `date`, `payload` (the full `contracts.Festival`)
- 2026 dates were verified against the SmartPuja 2026 Hindu festival calendar and the 2026 gazetted holiday list (sources in `app/data/festivals.py`):
  - Karwa Chauth 29 Oct, Dhanteras 6 Nov, Diwali 8 Nov, Bhai Dooj 11 Nov, Gurpurab 24 Nov.
- Each row has phases (teaser / build-up / last-minute / post), hero categories, an exact greeting (only for opted-in customers), `restricted_promos` (Navratri and Gurpurab: no meat or alcohol), a budget and delivery days by tier.
- The generator's festival **lift multipliers** live beside them in `festivals.lifts()`:
  - major (Diwali, Dhanteras): build-up visits ×1.35, last-minute ×1.55, hero categories ×2.2–2.4;
  - minor festivals and sales are smaller.

---

## 5. Live profile (`scoring/profile.py` → `contracts.CustomerProfile`)

Built from the DB rows on every call: no per-customer cache, ~6 ms p50 and ~17 ms p95 at 5,000 customers on SQLite. Only rows with `ts ≤ now` count, so `/simulate` events and time-travel apply instantly.

| Field | Derivation |
|---|---|
| `recency_days` | Days since the last purchase (since signup if none), clamped ≥ 0 |
| `orders_90d`, `aov`, `ltv` | Purchase events; `ltv` is net of returns |
| `rfm` | R/F/M quintiles (1–5) over the last 365 days of buyers, mapped to Champions / Loyal / Potential / At Risk / Hibernating / New / Lost. Also carries `orders_total`, `views_90d`, `days_since_active`, `tenure_days`, `spend_365d`, `vip_spend_365d` (p90), `offers_received`, `offers_declined` |
| `churn_risk` | Logistic regression (`scoring/churn.py`, AUC ≈ 0.78), see below |
| `uplift` | T-learner per offer type (§6) |
| `price_sensitivity` | 0.7 × coupon-use rate + 0.3 × share of orders below the category median |
| `category_affinity` | 60% spend share + 40% share of views in the last 90 days |
| `return_rate`, `discount_usage_rate` | Returns ÷ purchases; coupon orders ÷ orders |
| `points_*`, `tier` | Ledger replay up to `now`; points expiring within 30 days |
| `open_cart` | The latest add-to-cart that is newer than the last purchase and less than 72 h old (with `minutes`) |
| `last_offer_at`, `offers_7d`, `active_coupon` | SENT decisions plus campaign `offer_received` events |
| `policy` | `assign_policy()`: the first match in `POLICY_THRESHOLDS` (one config dict), in this order: high_returner → sleeping_dog → vip → cart_abandoner → dormant → at_risk → new_user → deal_hunter → window_shopper → default |

The churn model is trained on snapshots 60, 120 and 180 days before the end of the simulation:
- **label:** no purchase in the next 60 days;
- **features:** log recency, orders in 90 days, frequency trend, session trend, return rate, tenure and AOV;
- it is stored as plain coefficients in `churn_model.py`. Retrain with `python -m app.scoring.churn`.

---

## 6. Past campaigns, uplift and impact

| Campaign | Sent | Offer | Targeted | Control |
|---|---|---|---|---|
| Diwali 2025 | 13 Oct 2025, 8 days | 15% off ≥ ₹999 | 50% of eligible | 10% |
| Black Friday | 25 Nov 2025, 6 days | ₹300 off ≥ ₹1,999 | 35% | 10% |
| Lohri (Punjab only) | 9 Jan 2026, 5 days | free shipping | 60% of Punjab | 10% |
| Holi | 26 Feb 2026, 7 days | 2× points | 30% | 10% |
| Summer sale | 22 May 2026, 7 days | 10% off ≥ ₹799 | 40% | 10% |
| Independence Day | 12 Aug 2026, 5 days | ₹200 off ≥ ₹1,499 | 35% | 10% |

**Uplift (`scoring/uplift.py`):**
- **Model:** a T-learner per offer family (discount, points), with treated and control `GradientBoostingClassifier`s.
- **Control data:** each family's control arm comes from the same campaigns, plus eligible-but-untargeted customers. Targets were random, so they are a second, larger control.
- **Training data:** the seed-42 5,000-customer world (`python -m app.scoring.uplift`).
  - Retraining on other worlds reshuffles the per-type estimates, because the Holi points test is small (~900 treated).
  - So the shipped model is the one whose held-out sanity checks pass.
  - Pooling two worlds didn't improve it.
- **Feature parity:** features come from `build_profile()` at send time, so training equals serving.
- **Borrowed families:** free shipping and nudges borrow the discount family at a fixed strength, because the only shipping test (Lohri) was too small.
- **Export:** the trees are exported to plain Python (`uplift_model.py`), with no pickle.
- **Results:** the Qini curve beats random for both families. Held-out sanity checks by hidden type are stored in `MODEL["report"]`.

**Impact (`scoring/impact.py`):**
- Paid offers:

  ```
  cost   = giveaway (discount × basket, shipping fee, or points liability) × P(buy | offer)
  profit = (uplift − 0.01) × basket × margin − cost
  ```
- Zero-cost offers: `profit = max(uplift, 0) × basket × margin`, or negative when the predicted uplift is clearly harmful.
- Sure-things therefore come out negative for paid offers. That margin is what the engine saves by not discounting them.

**Experiments page (`scoring/experiments.py`):** treated vs the 10% control (campaigns), and SENT vs HELD_OUT (live decisions, purchase within 7 days).
- Margin saved on sure-things = coupon cost × control conversion ÷ treated conversion.
- On the seed-42 world, blanket 15% off lost money (ROI −0.07) while flat ₹ off returned about 3×.

---

## 7. Real Telegram users (`data/onboarding.py`)

A classmate's taps (categories, frequency, style, festivals) pick a persona:

| Answers | Persona |
|---|---|
| weekly + quality | VIP |
| weekly + balanced | cart abandoner, with a fresh open cart |
| monthly + balanced | at-risk |
| occasionally + balanced | window shopper |
| rarely | new user |
| deal | deal hunter |

A one-customer run of the same behaviour model then writes about 180 days of matching history (`E<id>-…`, `O<id>-…`), with a minimum number of orders so that the profile looks right from the first message.

Re-running `/start` replaces only that generated history; `/simulate` events are kept. Real users are never in the holdout, because a classmate with a silent bot would think it's broken.

## 8. Re-seeding safely
`python -m app.data.seed` replaces only synthetic `C…` customers and their rows. It keeps:
- real Telegram users (`TG…`);
- Customer Lab customers (`is_lab_bot`, or listed in `customer_bots`) and **all** their history;
- decisions, rules and offers.
