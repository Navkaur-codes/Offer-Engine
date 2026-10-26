# Study notes: explaining Holdout to the judges

> My personal prep notes (26 Oct 2026). Source of truth: `docs/final.md`, `docs/demo-script.md`, `docs/user-guide.md`, `docs/architecture.md`.

**Plan (under 1 hour):** 1 → 2 → 6 in depth (~10 min each) · quick pass over 3, 4, 5, 7, 10 (~10 min) · mock judge Q&A (~15 min) · cheat sheet.

## Progress checklist
- [x] 1. The problem and the idea (why "Holdout")
- [x] 2. How one decision is made (pre-gate → policy → agent → validator → fallback → logged)
- [x] 3. The Telegram bot and `/simulate` (commands section)
- [x] 4. Explanations (`/why`)
- [x] 5. Rules for marketers (layers, sentences, impact preview, versions)
- [x] 6. Incrementality (uplift, expected incremental profit, 10% holdout, Experiments)
- [x] 7. Personas / policies (incl. the sleeping dog)
- [x] 8. Customer Lab (commands + demo)
- [x] 9. Festivals and cultural safety
- [x] 10. AI budget and fallback
- [x] 11. Synthetic data realism
- [x] 12. Dashboard pages
- [ ] 13. How it was built (CLAUDE.md, parallel sessions), covered in the final answer only
- [ ] 14. Judge Q&A rehearsal (not done; user chose explanations only)

---

## Features

_(Mode: explanations only; I ask questions when I have them.)_

### 1. The problem and the idea ✅
- **Simple:** shops send discounts to everyone and count every sale as a win, but many would have bought anyway, so margin is wasted. Holdout asks first: *will this offer change what this customer does?*
- **Why "Holdout":** the holdout is the group that deliberately gets nothing, so you can measure what offers really caused.
- **3 ideas:** rules set limits, AI personalises inside them and is re-checked · incrementality first (predict extra profit, prove with 10% holdout) · never silent, never unexplained.
- **Numbers:** +₹91,760 incremental revenue (12 months) · ₹14,916 margin saved.
- **One-liner:** *"Holdout decides whether an offer will actually change what a customer does, and only pays the ones it will."*

### 2. How one decision is made ✅
- **Simple:** every trigger goes through a fixed pipeline of code the AI can't skip: Pre-gate → Policy → Allowed offers → AI agent → Validator → (retry / fallback) → Sent + logged.
- **Key facts:** one function `rules.engine.evaluate()` is used by pre-gate, the agent's `check_offer` tool and the final validator · AI is read-only (tools only look things up) · one Groq call, strict JSON, 20 s limit · retry once with the violations, then rules fallback · fallback also on timeout, 429, bad JSON, budget out · if AI says "no offer" while a profitable offer exists, rules send the best one · explanations built from numbers, never the AI's words · every status logged (SENT, QUEUED, HELD_OUT, NO_OFFER, BLOCKED) · property test: thousands of random decisions, nothing out of limits ever approved.
- **One-liner:** *"The AI only proposes; the same rule code that set the limits checks every offer before it goes out, and if the AI fails, the rules decide."*

### Customer types, deals and commands (from the start) ✅
**Two kinds of "type":**
- **Hidden response type** (the truth, the engine never sees it; only in synthetic data): **persuadable** (buys only if offered → target), **sure thing** (buys anyway → don't pay), **lost cause** (won't buy either way → don't waste), **sleeping dog** (buys *less* if contacted → leave alone). The engine has to infer this from behaviour via uplift.
- **Persona policy** (what the engine assigns live from scores, checked in this order; first match wins):

| Policy | Who (threshold) | Allowed deals |
|---|---|---|
| High returner | return rate ≥ 40%, ≥ 3 orders | bonus points, points reminder only (no discounts) |
| Sleeping dog | every offer type predicted to hurt **and** declined ("Not for me") at least once | **nothing proactive** |
| VIP | top 10% spend, bought in last 30 days, ≥ 3 orders | early access, 2× points, free shipping/express, points reminder; **no % discounts** |
| Cart abandoner | cart left 30 min – 72 h | ladder: nudge or free shipping first; after 24 h up to 5% off; bonus points |
| Dormant | inactive 120+ days | one win-back (≤ 15% off, free shipping, nudge), then 90 days quiet |
| At risk | churn ≥ 0.6 + 30 days quiet, or 60+ days quiet (≥ 2 orders, LTV ≥ ₹2,500) | win-back ≤ 20%, free shipping, points, nudge, only if uplift ≥ 5%; once a month |
| New user | joined ≤ 30 days, ≤ 1 order | ≤ 15% off, free shipping, nudge, points reminder |
| Deal hunter | uses discounts on ≥ 60% of orders, ≥ 2 orders | ≤ **10%** off, only basket ≥ **₹999**; nudge, points reminder |
| Window shopper | ≥ 8 views in 90 days, 0 orders | free shipping, flat ₹ off ≤ **₹150**, nudge, early access |
| Default | everyone else | global limits only |

**Offer catalogue (10 templates):** cart nudge, points reminder, early access (all ₹0) · free shipping, free express · bonus points 2–3× · % off a category (5–30%) · win-back % (10–20%, basket ≥ ₹999) · second-order welcome (10–15%) · flat ₹ off (₹50–500, basket ≥ ₹499).

**How a deal is chosen (funnel):** catalogue → remove what Global/Festival/Persona/Individual rules forbid (tighten only) → compute expected incremental profit for each (uplift × basket × margin − cost) → keep only ones that pay (free perks: ≥ 0; paid: > 0) → AI picks one + writes message → validator → if AI fails, fallback picks highest expected profit at the cheapest allowed value (e.g. lowest %).

**Commands:**
- Customer (private chat): `/start` · `/simulate` (cart, browse, purchase, inactive, points_expiry, festival, payday, persona; no args = button menu) · `/why` · `/history` (last 5, incl. no-offer) · `/offers` · `/profile` · `/pause` (7 days, `/pause 3`) · `/resume` · `/stop` · `/help`.
- Card buttons: ✅ Claim · ⏰ Remind me tonight (19:00) · 🙅 Not for me (category muted 14 days) · ❓ Why this?
- Admin only: `/summary` · `/killswitch on|off` · `/campaign run <policy>` · `/impersonate <id>` / `off`.
- Lab group: `/lab here | run [n] | who | persona <name> <state> | date <YYYY-MM-DD> | date off | reset` · `/why` (reply to a card). In the group address the bot as `/lab@navpreet_offers_bot`.

### 6. Incrementality and the Experiments numbers ✅
- **T-learner uplift:** two models trained on past campaigns that had a 10% control: model T = "chance to buy if offered" (trained on treated), model C = "chance to buy if not offered" (trained on control). **Uplift = T − C**, per customer and offer type. ("T" = two models.)
- **Measuring:** each campaign compared only with **its own** control (avoids Simpson's paradox). Incremental revenue = (treated conversion − control conversion) × treated customers × typical basket. Control groups < 20 people are reported as "unmeasured", not guessed.
- **Incremental profit** = incremental revenue × margin − coupon cost. Live (26 Oct): ≈ ₹24k extra margin − ₹22,559 coupon cost → **+₹1,722** (docs say ₹1,725; tiny drift). Small because the history includes a **blanket free-shipping** campaign (−₹24,320). That loss *is* the argument for targeting.
- **Precise version of the free-shipping loss:** its cost was only ₹1,010; the loss is because the 205 people who got it bought *less* than their control group (−₹88,918 incremental revenue). Untargeted, it hit sure-things and people who don't respond (or react badly) to offers.
- **Margin saved (₹14,916):** coupon money that a blanket offer would pay to people who'd have bought anyway (cost × control conversion ÷ treated conversion), i.e. what targeting avoids.
- **ROI by offer type:** flat ₹ off 1.9× · 2× points nearly free · free shipping blanket −₹24,320.
- **Qini curve:** if you target customers in order of predicted uplift, how much extra profit do you gain vs random targeting? Curve above the diagonal = the model ranks people better than random.
- **One-liner:** *"Every campaign is measured against its own control group, so ₹91,760 is revenue offers caused, not revenue that followed them; and the free-shipping loss shows exactly why untargeted offers waste money."*

### 10. AI budget and fallback ✅
- Groq `gpt-oss-120b`, one call ~2 s; at 80% of the daily token budget → `gpt-oss-20b`; at 100% → rules only. "Degraded AI" chip on the dashboard.
- Free tier ≈ 3 AI decisions/minute → extra ones get 429 → rules fallback (~25 ms). **By design, not a bug.**
- Campaigns and big Lab runs: AI only for the top 5 by expected profit; rules handle the rest.
- Daily digest numbers computed in code; AI only rewords; mismatched numbers → rewrite thrown away.

### 9. Festivals and cultural safety ✅
- 26 festivals/sales (Sep 2025 – Jan 2027), each with phases: teaser → build-up → last minute → post-festival; per-phase budgets; in build-up, discounts only on hero categories; restricted promotions (e.g. meat, alcohol) blocked by the validator.
- **Religion never inferred from a name.** Greetings only to customers who opted in at `/start`; text comes from the festivals table, never the AI; validator rejects any other greeting.
- Judging window = Karwa Chauth → Dhanteras → Diwali run-up.

### 11. Synthetic data realism ✅
- 12-month day-by-day simulation: sessions → views → carts → checkouts → orders; lognormal order values; seasonality, payday and festival lifts; churn; returns; deliberately messy fields. ~1,500 customers in production; Punjab-heavy tier-1/2/3 cities; UPI/COD/card.
- Benchmarks on the Realism page: top 20% ≈ 75% of revenue (Pareto), cart abandonment ≈ 69%, decaying retention curve, each with target band ✓/✗.
- Why synthetic: no real customer data allowed (privacy), and only synthetic data has the hidden truth to check the model against.

### 12. Dashboard page by page ✅
| Page | Why it exists (on-page note) | What's on it | Logic behind it | Demo |
|---|---|---|---|---|
| Sidebar/top bar | always visible controls | kill-switch dot, budget meter, degraded-AI chip, upcoming moments, bot link/QR, 🔒 admin, ⌘K, dark mode | kill switch = pre-gate check #1; budget > 80% shrinks caps | point at the dot + ⌘K |
| Overview | "See in 10 seconds whether offers make money that wouldn't have come anyway" | orange hero = incremental revenue vs holdout (12 mo); sent today, claim rate, budget, blocked; live stream; funnel; AI vs rules; margin protected; digest; upcoming moments | hero = Experiments maths; stream = decision log | open first, point at hero + margin |
| Decisions | every offer sent, held back or blocked, with the reason | table + filters in URL; drawer: Pipeline Lens ✓/✗/↺, explanation, each rule, agent tool calls/tokens, rejected alternatives, card preview | `decision_store` logs every status | filter Blocked → open one; open an AI one |
| Rules & policies | set the limits the AI must stay inside | 4 layer tabs; sentence cards with editable numbers; impact preview; History + revert; global hard limits can't be off | rules are DB rows; `describe()` makes the sentence; tighten-only | Persona → Deal hunter 10% → 8% → read preview → **don't save** (or revert) |
| Customers | who is in which policy now | recency × value scatter (colour + shape by policy), search/filter; drawer: scores in words, timeline, decisions, Run decision now (dry), Simulate trigger (real) | policy assigned live by thresholds | filter Cart abandoner → open one → Run decision now |
| Experiments | proof: treated vs 10% holdout | treated vs holdout, incremental revenue/profit, uplift by policy, ROI by offer type, Qini, festival lift; 30d/90d/12mo | each campaign vs own control; < 20 controls = unmeasured | 12 months → ROI table: flat ₹ off 1.9×, free shipping −₹24,320 |
| Festivals | plan budget/strategy per moment | 90-day phase calendar, strategy + budget per phase, hero categories, greeting preview "opt-in only" | festival layer rules; greetings from table only | show Diwali phases + opt-in badge |
| Realism | synthetic data behaves like real data | Pareto, cart abandonment, funnel, retention, seasonality, returns, each with band ✓/✗ | `scoring/realism.py` benchmarks | one glance |
| Playground | run the full pipeline without sending | customer/quick-pick, trigger, optional date, Run, step-by-step; force LLM failure toggle | `decide(dry_run=True)`: never stored or sent | Cart abandoner → Run; toggle failure → Run again |
| Campaign dry-run (⌘K) | preview a campaign | who gets what, cost, blocked + why, totals | rules score all; AI only top 5 | Deal hunter + budget → read totals |

**Demo order (5 min):** Overview hero → Telegram `/start`, `/simulate cart`, ❓ Why this? → `/simulate purchase` + `/simulate cart` (48 h block) → Overview stream → Playground (+ force failure) → Rules 10→8% preview → Experiments ROI → Realism glance → close line.

---

## My questions & answers

**Q: What does "Incrementality first. An offer must be expected to pay for itself in extra profit. A 10% holdout proves it afterwards." mean?**
- *Incremental* = **extra**: only the sales the offer *caused*, not the sales that would have happened anyway.
- **Before sending (prediction):** expected incremental profit = uplift × typical basket × category margin − offer cost. Example: uplift 10% (0.10) × ₹1,000 basket × 40% margin = ₹40 extra profit expected; a ₹50 discount costs ₹50 → −₹10 → **not sent**. Free shipping costing ₹30 → +₹10 → **allowed**. Zero-cost perks (2× points, early access, cart nudge) come first.
- **After sending (proof):** 10% of synthetic customers are randomly held out (decided, logged, but nothing sent). Treated group buys more than the holdout → that gap is what offers really caused (+₹91,760 revenue over 12 months).
- One-liner: *"Before sending we predict the extra profit; after sending the holdout measures it."*

**Q: When will the ₹92k (₹91,760) change?** (checked in `scoring/experiments.py`, `api/analytics.py` and the live API on 26 Oct)
- It is a **rolling last-365-days** window, recalculated from today's date (cached 10 min). It's built from two sources:
  1. **6 past campaigns** in the synthetic history (13 Oct 2025, 25 Nov 2025, 9 Jan, 26 Feb, 22 May, 12 Aug 2026), each vs its own 10% control. The 13 Oct 2025 one has already dropped out of the window. **The next one drops out on 25 Nov 2026**, so the number is stable through judging.
  2. **Live decisions:** SENT vs HELD_OUT, counting purchases within 7 days. Right now 22 live treated and 0 held-out → **"unmeasured"**, adds ₹0. It only starts counting once ≥ 20 held-out decisions exist (only synthetic customers are held out; real Telegram users never are).
- So it changes if: the window rolls past a campaign date · enough live synthetic decisions accumulate · the engine clock is moved (`/lab date …`, so always end with `/lab date off`) · the database is re-seeded (not allowed now).
- Profit can drift by a few rupees (₹1,725 in docs, ₹1,722 live today).
- Judge line: *"It's a rolling 12-month figure from campaigns with randomised control groups; live decisions join the number once there are enough held-out customers to measure fairly."*

**Q: What about the 90-day and 30-day views on Experiments?** (live API, 26 Oct)
| View | Incremental revenue | Profit | Margin saved | Why |
|---|---|---|---|---|
| 12 months | ₹91,760 | ₹1,722 | ₹14,916 | 5 campaigns in the window |
| 90 days | **₹29,304** | **₹5,412** | ₹893 | only the 12 Aug 2026 campaign (395 treated, 47 control) |
| 30 days | **₹0** | ₹0 | ₹0 | no campaign in the last 30 days; 22 live decisions, 0 held out → "unmeasured" |
- 90 days: the 12 Aug campaign leaves the window around **10 Nov**, after judging.
- 30 days showing ₹0 is honest, not broken: nothing to compare against yet. The Overview hero uses 12 months for this reason.
- Interesting point: 90-day profit (₹5,412) is *higher* than 12-month profit (₹1,722), because the 12 months include the loss-making blanket free-shipping campaign.

**Q: If we make an offer now (bot, Lab, Playground), will the Experiments numbers change?**
- **Your own Telegram offers / `/simulate`:** no. Real Telegram users are never held out, so there's no control to compare with; the decision is counted as "unmeasured" (treated count goes 22 → 23) and adds ₹0.
- **Playground / Run decision now:** no. Dry runs are never stored.
- **Lab rounds:** almost certainly no. Only Lab customers who are in the holdout create held-out decisions; it would take very many rounds to reach 20.
- **Big `/campaign run` on synthetic customers:** could eventually, because 10% are held out and ≥ 20 held-out decisions would switch the live comparison on (and it could move the number up *or* down). → **Don't run big campaigns before judging.**
- **Can a campaign *raise* the ₹92k?** Practically **no** (checked `bot/admin.py`, `scoring/experiments.py`). `/campaign run <policy> [n]` handles at most 25 synthetic customers per run (default 10), so ~2–3 held out per run → ~8 runs to reach 20. Even then, synthetic customers make no new purchases live, so treated and held-out both convert 0% → extra revenue ₹0 → number stays the same. Side effect: it uses up those customers' weekly offer caps, so demo picks may show "Blocked". **Don't run it to move the number; that would also look like gaming the result.**
- **What DOES change right away:** Overview tiles: sent today, claim rate, budget used, blocked by rules, the live stream, "who decided", the funnel. That's expected and good to show.

---

**Q: Easy way to explain the orange number and "margin saved"?**
- **Orange (₹91,760):** "Customers who got offers vs a similar group who got nothing. Offer group bought more; the difference over 12 months is ₹91,760: sales the offers *caused*, not sales that just happened."
- **Margin saved (₹14,916):** "When you give coupons to everyone, part of that money goes to people who'd have bought anyway. That wasted share is ₹14,916. We avoid it by not giving coupons to those people."
- Example: 100 coupons of ₹100; 30 coupon users would have bought anyway → ₹3,000 wasted = margin saved by targeting.

## Judge Q&A practice

---

## Issues seen
_(Anything that looked wrong in the live product. Report to the Main session; don't fix here.)_
- (minor, docs) Live incremental profit reads **₹1,722** (26 Oct) vs **₹1,725** in `final.md`/brief. Say "about ₹1.7k" or read it off the page.
- (wording, docs) "Blanket free shipping −₹24,320" is mostly *negative lift* (treated bought less than control, −₹88,918 revenue), not shipping cost (₹1,010). Not a bug; just know the precise reason if asked.

---

## Test cases to show the evaluator
| # | Where | Do | Expected (pass) | Proves |
|---|---|---|---|---|
| T1 | Telegram | `/start` → 3 taps → (opt-in) | consent note, then welcome perk card (picture, value, expiry, mono coupon, 4 buttons) | onboarding + profile + decision |
| T2 | Telegram | `/simulate cart` | offer card (nudge / free shipping / small %) | full pipeline live |
| T3 | Telegram | tap ❓ Why this? (or `/why`) | why you, why this offer, rejected alternatives, rules checked, decided by | explainability |
| T4 | Telegram | `/simulate purchase` then `/simulate cart` | blocked / no discount: "48 h after a purchase" reason | hard rule, never silent |
| T5 | Telegram | `/pause` → `/simulate cart` → `/resume` | BLOCKED (paused), then normal again | consent |
| T6 | Telegram | `/history`, `/profile` | last 5 incl. blocked; persona + scores in words | transparency |
| T7 | Telegram (admin) | `/impersonate <deal-hunter id>` → `/simulate cart` → `/impersonate off` | % ≤ 10, basket ≥ ₹999 | persona limits |
| T8 | Playground | VIP quick-pick → Run | early access / points / free shipping, **never % off** | persona rules |
| T9 | Playground | Cart abandoner → Run, then **force LLM failure** → Run | 1st: AI agent ✓ (or Rules fallback if rate-limited); 2nd: "Rules fallback", still valid, validator ✓ | fallback + same validator |
| T10 | Lab group | `/lab@navpreet_offers_bot run 3` (+ reply `/why`) | different offers per persona; sleeping dog gets nothing | personalisation + incrementality |
| T11 | Rules | Deal hunter 10% → 8%, read impact preview, **don't save** | customers affected + budget change shown | marketer control |
| T12 | Decisions | filter Blocked → open one; open an AI one | Pipeline Lens ✓/✗/↺, failing rule named, tool calls | audit trail |
| T13 | Experiments | 12 months → ROI table | +₹91,760; flat ₹ off 1.9×; free shipping −₹24,320 | proof it pays |
| T14 | Realism | glance | all benchmarks ✓ within band | data realism |
| Backup | — | kill switch on → `/simulate cart` → BLOCKED → **switch off** | blocked by kill switch | safety (only if asked) |
| Backup | terminal | `python docs/testing/run_scenarios.py` | 20 scenarios / 56 decisions pass (last run 26 Oct: 56/56) | automated black-box tests |
| Backup | — | mention | 362 backend tests incl. property test on `evaluate()` | rigour |

---

## Cheat sheet (one page)

**30-second pitch:** "Most shops send discounts to everyone and count every sale as a win, but many of those people would have bought anyway. Holdout asks one question first: will this offer change what this customer does? Marketers set limits as plain-English rules, an AI agent picks and words the offer inside them, and the same rule code re-checks every AI choice before it reaches Telegram. If the AI fails, the rules decide. A 10% holdout group proves what the offers really caused: about ₹92k of extra revenue over 12 months, and ₹15k of margin saved by not paying people who'd buy anyway."

**5 key numbers:** +₹91,760 incremental revenue (12 mo) · ₹14,916 margin saved · blanket free shipping −₹24,320 vs flat ₹ off 1.9× ROI · ~2 s per AI decision (~25 ms fallback) · 362 backend tests + 56/56 live scenario checks.
(Also: 10 policies · 26 festivals · ~1,500 synthetic customers · 10% holdout · 90 days ₹29,304 / 30 days ₹0 = no control yet.)

**6 phrases to remember:**
1. "Don't pay people who'd buy anyway."
2. "Rules set the limits; the AI personalises inside them."
3. "One `evaluate()` function decides what's legal, for the AI and the fallback alike."
4. "Never silent, never unexplained: even 'no offer' is logged with a reason."
5. "Every campaign is measured against its own control group."
6. "Religion is never guessed from a name; greetings are opt-in and never AI-written."

**If something goes wrong live:** "Rules fallback" = Groq free-tier limit, by design · Render slow = cold start, open `/health` · a "Blocked" = a rule doing its job, open `/why`.
