# Holdout: the complete feature guide

**Offers only where they change the outcome.**

| | |
|---|---|
| **Telegram bot** | [@navpreet_offers_bot](https://t.me/navpreet_offers_bot) |
| **Marketer dashboard** | https://offer-engine-nu.vercel.app |
| **API health** | https://offer-engine-n4jx.onrender.com/health |
| **Built for** | Punjab Jobs AI Bootcamp hackathon (J-PAL South Asia), 22–27 Oct 2026 |
| **Data** | 100% synthetic; no real or scraped personal data |

---

## 1. The problem and the idea

E-commerce teams send discounts to everyone and count every sale that follows as a win. But many of those customers would have bought anyway, so the discount simply gave away margin. Some customers even buy *less* when they're pestered.

**Holdout decides, for each customer and each moment, whether an offer will actually change what they do, and only then which offer and when.** It is named after the experiment design it is built on: a *holdout* is the group that deliberately gets nothing, so you can measure what offers really caused.

Three ideas run through the whole product:
1. **Rules set the limits; AI personalises inside them.** Marketers write limits as plain sentences. An AI agent picks and words the offer. **Every AI choice is re-checked by the same deterministic rule code before it is sent.**
2. **Incrementality first.** Every offer must be expected to pay for itself in *incremental* profit, and a 10% holdout proves the effect afterwards.
3. **Never silent, never unexplained.** A rules fallback decides whenever the AI can't, and every decision, including "no offer", is logged with a plain-English reason.

---

## 2. How one decision is made

```
Event (Telegram · Customer Lab · scheduler · dashboard)
  → live customer profile (RFM, churn risk, uplift per offer type, policy)
  → HARNESS — deterministic code the AI cannot skip:
      1. Pre-gate: kill switch · /stop · /pause · quiet hours · frequency · budget · holdout
      2. Effective policy: Global → Festival → Persona → Individual (each layer can only tighten)
      3. Allowed offers, each with an expected incremental profit
      4. AI agent (Groq, read-only tools, strict JSON, 20 s limit)
      5. Final validator: rules.engine.evaluate() on the exact offer AND message
      6. Retry once with the violations → otherwise the rules fallback decides
  → Telegram offer card (picture + caption + 4 buttons)
  → decision log + plain-English explanation → dashboard
```

**Guarantees built into this path:**
- **One function decides what is legal.** The pre-gate, the agent's own `check_offer` tool and the final validator all call `rules.engine.evaluate()`, so they can never disagree. A property test pushes thousands of random decisions through it, and nothing outside the limits is ever approved.
- **The AI is read-only.** Its tools can look up a profile, the policy, the allowed offers and impact estimates; it cannot write data or send messages.
- **Customer text is data.** Anything a Telegram user types is wrapped as untrusted data and escaped; it can't change rules, limits or the agent's role.
- **It never goes silent.** Timeouts, rate limits (429), invalid JSON, two failed validations or an exhausted AI budget all hand over to the deterministic fallback.
- **The AI can't talk itself out of a good offer.** If the agent says "no offer" while an allowed offer is expected to pay for itself, the rules send the best one and say so.
- **Explanations never use the AI's own words.** Reasons come from candidates, numbers and rule results, so an invented reason can't reach a customer, a judge or the log.

---

## 3. Features

### 3.1 Telegram bot: delivery channel and simulation console
| Feature | What it does |
|---|---|
| **`/start` onboarding** | Consent note, then 3 taps (categories, how often you shop, deal or quality) and an optional festival-greeting opt-in. It builds a profile with about 6 months of matching synthetic history and decides a **welcome perk**. |
| **`/simulate`** | `cart`, `browse`, `purchase`, `inactive`, `points_expiry`, `festival`, `payday`, `persona`. Each writes realistic events, updates the live profile and runs the full pipeline, so you watch the engine decide in real time. |
| **Offer cards as pictures** | Every sent offer arrives as a server-drawn card in the product's design system (graphite header, value in signal orange, coupon in mono, amber expiry chip), with the text as caption. If drawing ever fails, the text card is sent instead. |
| **4 buttons** | ✅ Claim · ⏰ Remind me tonight (19:00) · 🙅 Not for me (suppresses that category for 14 days) · ❓ Why this? Every tap is stored as an outcome. |
| **Transparency** | `/why` (explanation of the last decision), `/history` (last decisions, including blocked or no-offer), `/offers` (active coupons), `/profile` (your persona and scores in plain words). |
| **Consent** | `/pause`, `/resume`, `/stop` take effect immediately. No proactive messages 21:00–09:00 IST; they wait until morning. Replies to something you just asked for are never held back. |
| **Admin commands** | `/summary` (today's digest), `/killswitch on/off`, `/campaign run <policy>` (small batches, all rules apply), `/impersonate <customer>` (act as any synthetic customer to test or demo). |
| **Resilience** | Retries with backoff on Telegram 429/5xx, marks customers who blocked the bot as unreachable, ignores duplicate updates. |

### 3.2 Customer Lab: ten personas, live in a Telegram group
- 10 fixed synthetic customers (`C900001–C900010`): VIP, deal hunter, at-risk regular, new shopper, cart abandoner, window shopper, frequent returner, **sleeping dog**, dormant and festive gifter.
- They are voiced in rotation by "Lab Shopper" bots (1–10 bots; 4 today). Each posts activity ("🛒 Rohan added Printed Cotton T-Shirt ₹499 to cart 45 min ago…"), the Holdout bot answers with that customer's card, and the shopper replies in character (claim, ignore, decline or "why me?").
- Judges see **different personas get different offers under different rules**, and some get **nothing on purpose** (for example the sleeping dog: "no proactive offers for this customer").
- Commands: `/lab here | run [n] | who | persona <name> <state> | date | reset`. `/lab date 2026-11-06` time-travels the engine to any festival phase.
- Telegram bots can't message each other, so the backend runs every bot.

### 3.3 Scheduler: proactive moments
- **Abandoned carts:** every 5 minutes, a Telegram customer's cart left for 30 min to 6 h gets one nudge decision.
- **Morning flush (09:05):** offers that came due during quiet hours are re-decided with the morning's rules and consent.
- **Points expiry (10:00):** customers whose points expire within 3 days get a reminder decision, at most one every 3 days.
- **Daily digest (21:00):** today's summary goes to the admins.
- Synthetic customers are never messaged by jobs; a failing job never stops the others.

### 3.4 Marketer dashboard ("Signal" design)
Every page has a one-line "Why this page exists" note, and the most common actions are one click or ⌘K away.

| Page | What a marketer sees and does |
|---|---|
| **Overview** | Bento KPIs with one orange hero number, **incremental revenue vs the holdout (last 12 months)**; sent today, claim rate, budget used, blocked by rules; a terminal-style **live decision stream**; offer funnel; "who decided" (AI vs rules fallback); **margin protected** by not discounting sure-things; the AI daily digest; upcoming festival moments. |
| **Decisions** | Every decision with filters (status, decided by, policy, trigger, festival, search) kept in the URL. A drawer shows the **Decision Pipeline Lens** (Pre-gate → Policy → Agent → Validator → Sent, each ✓/✗/↺), the explanation, each rule ✓/✗, the agent's tool calls with timings and tokens, rejected alternatives and a Telegram card preview. |
| **Rules & policies** | Four layer tabs. Each rule is a **sentence with editable numbers** ("Deal hunters can get at most **10%** off, only on baskets above **₹999**"). Before saving, an **impact preview** shows the customers affected, the budget change and examples; every save is a version with **one-click revert**. Global hard limits can't be switched off. |
| **Customers** | Recency × value scatter by policy (colour and shape), search and filters, and a drawer with scores in plain words, timeline, past decisions, **Run decision now** and **Simulate trigger** buttons. |
| **Experiments** | Treated vs holdout, incremental revenue and profit, uplift by policy, **ROI by offer type**, Qini curve and festival vs baseline lift. Each campaign is compared with its own control group, and each chart has a one-sentence takeaway. |
| **Festivals** | 90-day phase calendar (teaser, build-up, last minute, post-festival), per-phase strategy and budget, hero categories, and a greeting preview with an "opt-in only" badge. |
| **Realism** | The synthetic data checked against real-world benchmarks (Pareto revenue share, cart abandonment, funnel, retention cohorts, seasonality, returns), each with its target band and ✓/✗. |
| **Playground** | Pick any customer, trigger and optional date, then **run the full pipeline without sending** and watch each step explained. A **"force LLM failure"** toggle proves the fallback still decides safely. |
| **Campaign dry-run** | Choose a policy or festival and a budget; see who would get what, the cost, what was blocked and why, and totals. The agent handles only the top 5 by expected profit; the rules score the rest. |
| **Always visible** | Kill switch, budget meter, AI token budget and a "degraded AI" chip, bot link and QR, light and dark mode. |

### 3.5 Rules marketers can read
Rules are **data** (database rows), never `if persona == …` code. Each renders as a sentence through its own `describe()`.

| Layer | Examples |
|---|---|
| **Global (hard limits)** | margin guard (discount ≤ category margin − 5 points); offers per 7 days and minimum gap; daily budget, with caps shrinking above 80% use; one active coupon; no % or ₹ discount within 48 h of a purchase; quiet hours 21:00–09:00 IST; message rules (≤ 280 characters, no banned phrases, no competitor names, every number in the text must match the offer) |
| **Festival** | phase budgets; in build-up, discounts only on the festival's hero categories; restricted promotions per festival (for example meat or alcohol) |
| **Persona (10 policies, assigned live from scores)** | VIP: early access, 2× points, free shipping, **no % discounts** · deal hunter: at most 10% with a ₹999 minimum basket · at-risk: win-back only when the offer moves them · new user · cart abandoner: nudge → free shipping → 5% · window shopper: at most ₹150 · high returner: points only · **sleeping dog: no proactive offers** · dormant: one win-back, then 90 days of quiet · default |
| **Individual** | `/stop`, `/pause`, 14-day "Not for me" suppression per category |

A lower layer can only make limits **tighter**; the global margin guard and hard caps can never be exceeded.

### 3.6 Incrementality engine
- **Hidden response types.** Every synthetic customer secretly is a *persuadable, sure-thing, lost cause* or *sleeping dog*. The engine never sees this; it has to infer it from behaviour, as in real life.
- **T-learner uplift model** trained on past campaigns that had a 10% control group. For each customer and offer type it predicts how much the offer changes the chance to buy.
- **Expected incremental profit** = uplift × typical basket × category margin − offer cost. Only offers with positive expected incremental profit are allowed; **zero-cost perks come first** (cart nudge, early access, 2× points).
- **Sleeping dogs** (offers make them *less* likely to buy, and they have declined offers before) are never contacted proactively.
- **10% holdout** of synthetic customers: decided as usual but nothing is sent, so the Experiments page can measure what offers caused.

### 3.7 Festival-aware and culturally safe
- 26 festivals and sales from Sep 2025 to Jan 2027 with verified 2026 dates and phases. The judging window falls in the Karwa Chauth → Dhanteras → Diwali run-up.
- **Religion is never inferred from a name.** Festival greetings go only to customers who opted in during `/start`, and the greeting text comes from the festivals table, never from the AI; the validator rejects any other greeting.
- Restricted promotions per festival are blocked by the validator.

### 3.8 AI that stays within budget
- Groq `openai/gpt-oss-120b` (one call per decision, about 2 s), stepping down to `gpt-oss-20b` at 80% of the daily token budget and to rules-only at 100%.
- Campaigns and big Lab runs use the AI only for the top 5 customers by expected profit; the rules handle the rest.
- The daily digest's numbers are computed in code; the AI may only reword them, and a rewrite whose numbers don't match is thrown away.

### 3.9 Realistic synthetic data
- Day-by-day simulation of 12 months: sessions → views → carts → checkouts → orders, lognormal order values, seasonality, payday and festival lifts, churn hazard, returns and deliberately messy fields.
- About 1,500 customers in production (5,000 locally in about 30 s), with Punjab-heavy tier-1/2/3 cities and UPI/COD/card payments.
- Benchmarks (all within range): top 20% of customers ≈ 75% of revenue; cart abandonment ≈ 69%; a decaying retention curve. Full data dictionary: [`data-dictionary.md`](data-dictionary.md).

---

## 4. Results (live, 26 Oct 2026)
| Metric | Value |
|---|---|
| Incremental revenue vs holdout (12 months) | **+₹91,760** |
| Incremental profit | **+₹1,725** |
| Margin saved by not discounting sure-things | **₹14,916** |
| ROI by offer type | flat ₹ off 1.9× · 2× points nearly free · **blanket free shipping −₹24,320** (went to people who'd buy anyway, the case for targeting) |
| Offers that would send in a scratch run of 200 decisions | 79%, mostly zero-cost perks · 0 validator failures |
| Decision time | ~2 s with the AI (one call) · ~25 ms by the rules fallback |
| Backend tests | **362 passing**, including a property test on `evaluate()`, LLM failure and retry cases, and every fallback message checked by the validator |

---

## 5. Technology
- **Backend:** Python 3.11, FastAPI, SQLModel, Pydantic v2, APScheduler, python-telegram-bot 21 (webhook), Groq, numpy/pandas/Faker/scikit-learn, Pillow; pytest + hypothesis; ruff.
- **Frontend:** React, Vite, TypeScript, Tailwind v4, shadcn/ui (restyled), TanStack Query/Table, Recharts, cmdk; each page loads on demand; Lighthouse accessibility 100 on every page.
- **Hosting (free tiers):** Render (API and bot), Neon Postgres, Vercel (dashboard), cron-job.org keep-alive.
- **Secrets** live only in host settings; the repo holds variable names only.

## 6. How it was built
Five Claude Code sessions worked in parallel on separate git worktrees, coordinated through files in the repo: `CLAUDE.md` (permanent rules and non-negotiables), `docs/claude-progressive.md` (the current phase), `docs/contracts.md` and `app/ports.py` (shared interfaces with stubs, so all sessions could build at once), and `docs/detective.md` (traps every request is checked against). An integrator session merged the work at five gates, each with full tests, a smoke test, a deploy and live checks. The human made every commit.
