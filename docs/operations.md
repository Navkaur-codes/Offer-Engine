# Operations runbook

How to run, deploy, monitor and fix Holdout. Commands are for Windows (PowerShell or Git Bash) from the repository root unless stated otherwise. **Never paste secret values into chat, issues or commits.**

## 1. Where things run

| Piece | Where | Notes |
|---|---|---|
| API + Telegram bot + scheduler | Render free web service `offer-engine` (Docker, `backend/Dockerfile`, region Singapore) | auto-deploys on every push to `main`; https://offer-engine-n4jx.onrender.com |
| Database | Neon Postgres (free tier, 0.5 GB) | about 1,500 synthetic customers |
| Dashboard | Vercel project, root directory `frontend`, framework Vite | auto-deploys on every push to `main`; https://offer-engine-nu.vercel.app |
| Keep-alive | cron-job.org pings `/health` every 10 minutes | Render's free tier sleeps after 15 idle minutes |
| LLM | Groq (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`) | free tier: about 3 agent decisions a minute; extra ones fall back to rules by design |

## 2. Environment variables

Names only; values live in `.env` locally and in the Render and Vercel settings. All values must be on one line.

| Variable | Where | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Render | the Holdout bot (`@navpreet_offers_bot`) |
| `TELEGRAM_WEBHOOK_SECRET` | Render | random string; part of the webhook path and header check |
| `PUBLIC_BASE_URL` | Render | the Render URL; the webhook registers itself on boot |
| `CUSTOMER_BOT_TOKENS` | Render | one-line JSON `[{"token":"…"},…]` for the 1–10 Lab Shopper bots |
| `ADMIN_TELEGRAM_IDS` | Render | comma-separated Telegram user ids allowed to use admin and `/lab` commands |
| `LAB_GROUP_CHAT_ID` | Render (optional) | normally saved automatically by `/lab here` |
| `GROQ_API_KEY` | Render | LLM access |
| `GROQ_MODEL_AGENT`, `GROQ_MODEL_FAST` | Render | `openai/gpt-oss-120b`, `openai/gpt-oss-20b` |
| `LLM_DAILY_TOKENS_AGENT`, `LLM_DAILY_TOKENS_FAST` | Render (optional) | daily token budgets (defaults 80,000 and 400,000) |
| `FORCE_LLM_FAIL` | Render (optional) | `1` switches the AI off for everyone (testing only) |
| `DATABASE_URL` | Render | Neon connection string (`postgresql://…`); SQLite locally |
| `ADMIN_PASSCODE` | Render | dashboard write access (`X-Admin-Passcode`) |
| `CORS_ORIGINS` | Render | `http://localhost:5173,https://offer-engine-nu.vercel.app` |
| `TZ` | Render | `Asia/Kolkata` |
| `DEMO_TIME_OVERRIDE` | Render (optional) | e.g. `2026-11-06` to time-travel; leave empty in production |
| `VITE_API_URL`, `VITE_USE_MOCKS` | Vercel | API URL and `0` |

## 3. Run locally

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -e "backend[dev]"
```

```bash
python -m app.data.seed --customers 5000 --seed 42
```

```bash
uvicorn app.main:app --reload --app-dir backend
```

```bash
cd frontend && npm i && npm run dev
```

- Without `TELEGRAM_BOT_TOKEN` the bot and scheduler are off and everything else works. Without `GROQ_API_KEY`, every decision is made by the rules fallback.
- To test the bot locally, use a **separate dev bot** with `python -m app.bot --polling`. **Never poll with the production token:** it deletes the production webhook.

## 4. Tests

```bash
pytest backend/tests -q
```

```bash
ruff check backend
```

```bash
cd frontend && npm run lint && npm run build
```

Black-box checks against the live engine (dry runs, nothing sent): `python docs/testing/run_scenarios.py` (see [`testing/README.md`](testing/README.md)).

`backend/tests/conftest.py` pins other teams' ports to stubs in unit tests; mark a test `@pytest.mark.real_ports` to use the real modules.

## 5. Deploy

1. All tests and lint green on `main`.
2. `git push origin main`. Render rebuilds in about 3–5 minutes; Vercel in about 1 minute.
3. Check: `/health` shows the expected `version`, every port `real` and a sensible `llm_budget.mode`; the dashboard loads (hard refresh with Ctrl + Shift + R); a Playground run returns a decision.

Database changes are applied at startup by `db.init_db()` (create missing tables plus small idempotent migrations).

## 6. Daily checks

| Check | How | Healthy |
|---|---|---|
| API up | `GET /health` | `ok: true`, `bot: true`, no `stub` ports |
| AI budget | `/health` → `llm_budget` | `mode` is `70b` (120B model); `8b` or `rules` means today's budget is used up; it resets at midnight IST |
| Scheduler | `GET /api/scheduler` | `running: true` with 4 next run times |
| Keep-alive | cron-job.org dashboard | a 200 every 10 minutes |
| Kill switch | dashboard sidebar dot | off |

## 7. Common tasks

| Task | How |
|---|---|
| **Stop all sends now** | dashboard kill switch, `/killswitch on` in Telegram (admin), or `POST /api/settings/killswitch {"on":true}` |
| Edit a rule | dashboard → Rules → change the number → check the impact preview → Save; revert from History |
| Test as a fresh customer | copy a customer id from the dashboard's Customers page (filtered by policy), then in your bot chat `/impersonate <id>` … `/impersonate off` (admin only; lost on restart). Policies drift as real time passes, so pick the id on the day |
| Run a scheduler job now | `POST /api/scheduler/run/{job}` with the passcode |
| Customer Lab setup | add the Holdout bot and Lab Shopper bots to the group, then `/lab@navpreet_offers_bot here` once |
| Run Lab rounds | `/lab@navpreet_offers_bot run 3` (each round counts toward that customer's weekly cap) |
| Time-travel the Lab | `/lab@navpreet_offers_bot date 2026-11-06`, and always finish with `/lab date off` (it moves the clock for the whole process) |
| Rebuild Lab customers | `/lab@navpreet_offers_bot reset` (rebuilds history; the decision log is kept) |
| Re-seed Neon | from `backend`, with `DATABASE_URL` set to the Neon URL in that shell only: `..\.venv\Scripts\python -m app.data.seed --customers 1500 --seed 42`, then remove the variable. Real Telegram users, Lab customers, decisions and rules survive. It changes the Experiments numbers, so avoid it near judging |

## 8. Judging-window settings (revert afterwards)

To let a judge go from `/start` straight to `/simulate cart` and get an offer, and to keep Lab customers usable after testing, three global rules were relaxed on the Rules page on 25–26 Oct:

| Rule | Normal | Judging |
|---|---|---|
| `G_FREQ` minimum gap between offers | 2 days | 0 |
| `G_FREQ` offers per 7 days | 3 | 10 |
| `G_ONE_COUPON` active coupons | 1 | 2 |

**After judging:** dashboard → Rules → Global → History on each card → revert to the earlier version. All other limits were never changed.

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Bot silent | Render asleep or redeploying; webhook lost | open `/health` and wait for it; check Telegram `getWebhookInfo` (the URL must be the Render webhook path); redeploy if needed. Never poll with the production token |
| "😅 Something went wrong" in the bot | an exception in a handler | Render logs → search `handler error`; the line names the exception type and step |
| Every decision says "Rules fallback" | Groq rate limit (429), daily token budget used up, or `FORCE_LLM_FAIL` set | expected under load; check `/health` → `llm_budget`; the budget resets at midnight IST |
| `/simulate cart` → "Holding off" or "Blocked" | a rule did its job (frequency, active coupon, 48 h after purchase) | the reply names the rule; use `/impersonate` with a fresh synthetic customer for demos |
| Lab customers all "Blocked" | they reached the weekly cap after many rounds | wait, raise the weekly cap for a demo, or show other personas |
| Dashboard shows old name or data | browser cache | Ctrl + Shift + R |
| Dashboard CORS errors | Vercel URL missing from `CORS_ORIGINS` | add it on Render and redeploy |
| Offer cards arrive as text only | image rendering or `send_photo` failed (it falls back on purpose) | Render logs → `card image`; text cards still work |
| Postgres `DataError` on ids | a 32-bit column | Telegram ids must be BIGINT; `init_db()` upgrades known columns |

## 10. Backup plan

If Render is down during judging: run the API locally (section 3) with the production `.env`, and run the bot with polling **only after** confirming Render is really down (polling replaces the webhook). Re-register the webhook by redeploying Render afterwards.
