# API reference

Base URL (production): `https://offer-engine-n4jx.onrender.com` · locally `http://localhost:8000`. Interactive docs: `/docs` (Swagger UI) and `/openapi.json`.

- Everything is JSON. Money is in whole rupees (integers); times are ISO 8601 in Asia/Kolkata.
- **Reads are public** so the dashboard can be browsed. **Writes need the header `X-Admin-Passcode`**: `401` means a wrong passcode, `503` means the server has no `ADMIN_PASSCODE` configured.
- Models (`Decision`, `DecisionLight`, `CustomerProfile`, `Rule`, `Kpis`, `ExperimentStats`, `RealismStats`, …) are defined in `backend/app/contracts.py` and described in [`contracts.md`](contracts.md).

## Service

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{ok, version, contracts, now, bot, ports: {name: "real"\|"stub"}, llm_budget: {agent, fast, mode}}` |
| POST | `/telegram/webhook/{secret}` | Telegram webhook. Needs the path secret **and** the `X-Telegram-Bot-Api-Secret-Token` header; otherwise `403` |

## Meta and settings

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/meta` | – | bot username, bot link, Lab group link, server time, demo time override, port status |
| GET | `/api/settings/killswitch` | – | `{on, changed_at}` |
| POST | `/api/settings/killswitch` | admin | body `{on: bool}` → `{on, changed_at}`. While on, every decision is BLOCKED |
| GET | `/api/budget` | – | today's spend, cap and % used, plus the active festival `{name, phase, days_to, budget_left}` |

## Analytics

| Method | Path | Returns |
|---|---|---|
| GET | `/api/today?day=` | today's offer money from the decision log: `{decisions, sent, spent, expected_incremental_profit, no_offer, margin_kept, blocked, held_out}`; `margin_kept` = for each NO_OFFER decision, what its costliest allowed offer would have cost |
| GET | `/api/kpis?day=` | `Kpis`: sent today, claim rate, budget used, blocked by rules, agent/fallback share, and `incremental_revenue` and `margin_saved` over the **last 12 months**; `deltas` vs yesterday (null when there's nothing to compare) |
| GET | `/api/experiments?start=&end=` | `ExperimentStats`: treatment vs control, incremental revenue and profit, margin saved on sure-things, uplift by policy, ROI by offer type, Qini points, festival vs baseline. Each campaign is compared with its own control |
| GET | `/api/realism` | `RealismStats`: benchmark statistics with target bands and sources |
| GET | `/api/digest?day=` | `{day, text, generated_by}`: the daily digest |

## Decisions

| Method | Path | Returns |
|---|---|---|
| GET | `/api/decisions?status=&decided_by=&policy=&trigger=&festival=&q=&limit=&cursor=` | `{items: DecisionLight[], next}`. Page with `cursor=next` (an ISO timestamp) |
| GET | `/api/decisions/{id}` | full `Decision`: profile snapshot, context, effective policy, candidates, agent trace, validation, explanation, outcome |
| GET | `/api/decisions/stream` | Server-Sent Events: `event: decision` with a `DecisionLight` for each new decision; a keep-alive comment every 20 s |

`status` is one of `SENT`, `QUEUED`, `HELD_OUT`, `NO_OFFER`, `BLOCKED` (`DRY_RUN` for Playground and dry-run results, which are never stored). `decided_by` is one of `AGENT`, `AGENT_RETRY`, `RULES_FALLBACK`, `BLOCKED_PREGATE`, `HOLDOUT`.

## Customers, Playground and campaigns

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/customers?q=&policy=&limit=&cursor=` | – | `{items: CustomerProfile[], next}` (cursor = last customer id) |
| GET | `/api/customers/{id}` | – | `{profile, events, decisions}` |
| POST | `/api/customers/{id}/simulate` | admin | body `{trigger, meta}` → a real `Decision` (stored, marked `initiated_by: admin`) |
| POST | `/api/playground/run` | – | body `{customer_id, trigger, meta, now?}` → a `Decision` with status `DRY_RUN`; nothing is stored or sent. `meta.force_llm_fail: true` forces the rules fallback for this run only |
| POST | `/api/campaigns/dry-run` | – | body `{policy?, festival?, offer_ids?, budget, limit}` → `{rows: DecisionLight[], totals: {customers, would_send, no_offer, blocked, over_budget, cost, expected_incremental_profit}}`. Uses `decide_batch`: the agent only for the top 5 |

Triggers: `welcome`, `cart_abandoned`, `browse_interest`, `inactivity`, `points_expiry`, `festival`, `payday`, `campaign`, `lab`, `manual`. Typical `meta`: `{category, item, value, minutes}` for carts, `{category, views}` for browsing, `{days}` for inactivity.

## Rules

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/rules?layer=` | – | `Rule[]`, each with its plain-English `description` |
| PATCH | `/api/rules/{id}` | admin | body `{params?, enabled?, priority?}` → the new `Rule` version. Global hard limits can't be disabled |
| POST | `/api/rules/preview` | – | body `{rule}` (the edited rule) → `{customers_affected, budget_delta, examples, sample_size}` on a 500-customer sample |
| GET | `/api/rules/{id}/versions` | – | `Rule[]` history |
| POST | `/api/rules/{id}/revert/{version}` | admin | restores that version as a new version |

## Catalogue and festivals

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/offers` | – | `Offer[]` |
| PATCH | `/api/offers/{id}` | admin | updated `Offer` |
| GET | `/api/festivals` | – | `Festival[]` with phases, hero categories, greeting, restricted promotions and budgets |
| PATCH | `/api/festivals/{id}` | admin | updated `Festival` |

## Scheduler

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/scheduler` | – | `{running, next_runs: {job: iso_time}}` |
| POST | `/api/scheduler/run/{job}` | admin | runs `cart_abandonment`, `flush_quiet_queue`, `points_expiry`, `personal_picks` or `daily_digest` now; `personal_picks` also returns `blocked`, `no_offer`, `spent`, `lab_posting` and one `rows[]` entry per customer (name, Telegram/Lab, top category and share, policy, status, explanation title, decided by, cost) |

## Examples

```bash
curl https://offer-engine-n4jx.onrender.com/health
```

```bash
curl -X POST https://offer-engine-n4jx.onrender.com/api/playground/run -H "content-type: application/json" -d "{\"customer_id\":\"C000129\",\"trigger\":\"cart_abandoned\",\"meta\":{\"minutes\":40}}"
```

```bash
curl -X POST https://offer-engine-n4jx.onrender.com/api/settings/killswitch -H "content-type: application/json" -H "X-Admin-Passcode: <your passcode>" -d "{\"on\":true}"
```
