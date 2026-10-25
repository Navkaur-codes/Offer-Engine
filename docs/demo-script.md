# Demo script: Holdout (5 minutes, plus 2 minutes of backup)

> For presenting live to judges. Times are cumulative. **Bold** lines are what to say; the rest is what to do.
> Screen setup: phone (or Telegram Desktop) on the left, the dashboard at https://offer-engine-nu.vercel.app on the right, Overview open.

## Before you start (10 minutes earlier)
- [ ] Open https://offer-engine-n4jx.onrender.com/health. It wakes Render; check `"bot": true`, all ports `real`, and `llm_budget.mode` is `70b` or `8b`.
- [ ] Dashboard: the kill switch is **off** (the sidebar dot) and the admin passcode is entered (needed for rule edits).
- [ ] Telegram: in the Customer Lab group, `/lab@navpreet_offers_bot who` lists the 10 Lab customers. If the engine clock was moved, run `/lab date off`.
- [ ] **Rehearse on your own phone without new accounts:** `/impersonate C000129` (admin only) makes your chat act as a fresh synthetic customer. Then `/simulate cart` → picture card → **❓ Why this?** → `/simulate purchase` + `/simulate cart` (blocked by the 48 h rule) → `/impersonate off`. Other fresh picks: `C000075` (VIP), `C000056` (deal hunter). Impersonation is kept in memory, so redo it after a Render restart.
- [ ] **Don't run the Lab the day before the demo.** Every round counts toward each Lab customer's "3 offers per 7 days"; a capped Lab shows mostly "Blocked" (honest, but not the story you want to tell first).
- [ ] Your own account: send `/stop`, then `/start` again, so the demo begins with a fresh welcome.
- [ ] Rules → Global shows the **judging settings**: frequency cap "at least **0** days apart" and "**2** active coupons" (set 25 Oct so `/start` → `/simulate cart` gives an offer). The 3-offers-per-7-days cap stays. Revert both under History after judging.
- [ ] Quiet hours (21:00–09:00 IST) only hold back **proactive** sends. Everything in this script is customer- or admin-initiated, so it works at any hour.

---

## 0:00 – 0:30 · The problem
**"Most discount engines send 20% off to everyone and count every sale as a win. But many of those people would have bought anyway. That's margin thrown away. Our engine asks one question first: will this offer change what this customer does? If not, it doesn't pay them."**

Point to the Overview hero number (incremental revenue vs holdout) and the "margin protected by not discounting sure-things" callout.

## 0:30 – 1:30 · A real customer on Telegram
1. `/start` → answer the 3 taps (categories, how often, deal or quality).
   **"It builds my profile and history from three taps, then the engine decides my welcome. Here's my card: exact value, expiry, coupon, four buttons."**
2. `/simulate cart`
   **"I just abandoned a cart. That event goes through the whole pipeline: guardrails, my policy, the AI agent, then the rule validator, before anything is sent."**
3. Tap **❓ Why this?**
   **"Every decision explains itself: why me, why this offer, what was rejected and why, which rules were checked, and whether the AI or the rules decided."**

## 1:30 – 2:15 · Guardrails you can see
4. `/simulate purchase`, then `/simulate cart`
   **"I just bought something, so the 48-hour rule blocks any discount, and the bot says so instead of going silent."**
5. On the dashboard, the live stream shows all four decisions, tagged **AI agent** or **Rules fallback**.
   **"Blocked and no-offer decisions are logged too. Nothing is hidden."**

## 2:15 – 3:15 · Customer Lab: ten personas, ten different answers
6. In the Customer Lab group: `/lab@navpreet_offers_bot run 3`
   **"These are ten synthetic shoppers voiced by bots. Watch: the VIP gets early access, never a discount. The deal hunter gets a capped discount with a minimum basket. And some get nothing at all, because they'd buy anyway or an offer would annoy them. That's the sleeping-dog policy."**
7. Reply `/why` to one of the Offer bot's cards for the explanation in the group.

## 3:15 – 4:15 · The dashboard: trust and control
8. **Playground:** click the **Cart abandoner** quick-pick (`C000129` Wishi), trigger `cart_abandoned`, Run. Other good picks (checked 26 Oct): VIP `C000075` Krish → early access, deal hunter `C000056` Gautami → 5% off ethnic wear with a minimum basket. **Don't use Lab customers here:** after many Lab rounds they hit "3 offers per 7 days" and show Blocked.
   **"This is the Decision Pipeline Lens: pre-gate, policy, agent, validator, sent. Here are the agent's tool calls and every rule ✓ or ✗."**
   Toggle **force LLM failure** → Run again.
   **"If the AI fails, times out or runs out of budget, the deterministic fallback decides, and it's checked by the same rule code. The bot never goes silent."**
9. **Rules:** change "Deal hunters get at most 10%" to **8%**.
   **"Marketers edit sentences, not JSON. Before saving I see how many customers and how much budget this affects. Every save is a version with one-click revert."** (Revert after showing it.)

## 4:15 – 5:00 · Proof it pays
10. **Experiments:** treated vs holdout bars, uplift by policy, margin saved.
    **"Every campaign is compared with its own control group. Over 12 months offers caused about ₹92k of extra revenue, and we saved about ₹15k of margin by not discounting people who'd buy anyway. Look at ROI by offer type: flat ₹ off pays back nearly 2×, but blanket free shipping *lost* money, because it mostly went to people who'd have bought anyway. That's exactly why we target."**
    (Numbers as of 25 Oct; read them off the page on the day.)
11. **Realism** (one glance): **"The data is synthetic but behaves like real shoppers: Pareto revenue, about 70% cart abandonment, churn, seasonality, all checked against benchmarks."**

**Close: "Rules set the limits, the AI personalises inside them, and every AI choice is re-checked before it reaches a customer. And we only pay people when it changes what they do."**

---

## Backup (if asked, or if something is slow)
| Question / problem | Show |
|---|---|
| "What if the AI says something wrong?" | Playground, force LLM failure; or Decisions → a decision with `AGENT_RETRY` / `RULES_FALLBACK` and its violations |
| "Festivals?" | Festivals page; in the Lab, `/lab@navpreet_offers_bot date 2026-11-06` (Dhanteras), `run 2`, then **`/lab date off`** |
| "Is consent respected?" | `/pause` → `/simulate cart` gives a blocked decision; `/resume`. Festival greetings only for opted-in customers |
| "Prompt injection?" | Customer text is passed as data; the agent's tools are read-only and the validator re-checks every output |
| "Kill switch?" | Sidebar dot → on; `/simulate cart` → BLOCKED; switch it **off** again |
| Render is slow (cold start) | Wait for `/health`; the dashboard shows mock-free data once it's up |
| Groq is rate-limited | Nothing to fix: decisions show `RULES_FALLBACK` and keep flowing. Say so; it is the design |
