# Voiceover script: Holdout demo video

> A screen recording with your voice, about **7 minutes** (a **3-minute short cut** is at the end).
> Every scene says **what to click**, **what to say** (simple words), and **the proof on screen**.
> Read the numbers off the page on the day; they can drift by a few rupees.

---

## Before you record (15 minutes earlier)

**Setup**
- [ ] Screen: dashboard https://offer-engine-nu.vercel.app on the right, **Telegram Desktop** on the left (your chat with `@navpreet_offers_bot` + the **Customer Lab** group).
- [ ] Open https://offer-engine-n4jx.onrender.com/health once to wake the server.
- [ ] Dashboard: kill-switch dot **off**, admin passcode entered (🔒 in the top bar).
- [ ] Telegram: send `/stop`, then you'll do `/start` fresh on camera.
- [ ] Record **between 09:00 and 21:00 IST** so the Personal-picks DM reaches you live (at night it waits until 09:00 by design).
- [ ] Personal picks needs the merged build with commit `f122fca`. Check that Overview → Automations shows a **Personal picks** row.
- [ ] Do a full dry run once, but **don't press Personal picks "Run now" more than once or twice before recording**: each run uses one of each Lab customer's 10 offers per week.

**Recording**
- [ ] Use OBS or the Windows Game Bar (Win + Alt + R) at 1080p. Zoom the browser to 110–125% so text is readable.
- [ ] Record the voice separately if you can, and keep each scene as its own clip. A mistake then means re-recording one scene, not the whole video.

---

## Scene 1 · The problem (0:00 – 0:25)
**Show:** Overview page.

**Say:**
"Online shops give discounts to everyone. But many of those people would have bought anyway, so the shop simply loses money. Our project, **Holdout**, asks one question before every offer: *will this offer change what this customer does?* If not, we don't give it."

**Proof on screen:** the orange hero number, **incremental revenue vs holdout**.

---

## Scene 2 · The data (0:25 – 0:55)
**Show:** sidebar → **Realism**.

**Say:**
"We were not allowed to use real customer data, so we built a realistic shop: about 1,500 shoppers, simulated day by day for a whole year, with visits, carts, orders, returns, Diwali and payday rush. We checked it against real e-commerce numbers. The top 20% of customers bring about 75% of the money, and about 70% of carts are abandoned, just like real shops."

"Each shopper also has a hidden type the engine is never told. Some buy only if offered, some buy anyway, some never buy, and some get annoyed by offers. The engine has to work this out from behaviour."

**Proof on screen:** each benchmark with its real-world range and ✓.

---

## Scene 3 · Past campaigns (0:55 – 1:25)
**Show:** **Experiments** → switch to the **90 days** view.

**Say:**
"During that year the shop ran six campaigns, like Black Friday and Independence Day. Each time, a random 10% of customers got nothing. That's the control group. Because they were picked at random, the only difference between the two groups is the offer. So whatever extra the offer group bought, the offer caused."

"For example, the Independence Day campaign: 395 customers got the offer, 47 didn't, and the offer brought in about ₹29,000 extra."

**Proof on screen:** treated vs control bars; 395 vs 47.
*(Optional: show the six campaigns in `backend/app/data/generator.py`, line 156.)*

---

## Scene 4 · A real customer joins (1:25 – 2:05)
**Show:** Telegram → `/start` → tap categories, how often you shop, deal or quality → (opt in to a festival).

**Say:**
"Now I'm a real customer on Telegram. I answer three quick questions. From that, the engine builds my profile and history, and decides my welcome offer."

"This card has the exact value, the expiry date, a coupon code and four buttons: Claim, Remind me tonight, Not for me, and Why this?"

**Proof on screen:** the picture card with value, expiry chip, coupon and buttons.

---

## Scene 5 · One decision, explained (2:05 – 2:45)
**Show:** `/simulate cart` → new card → tap **❓ Why this?**

**Say:**
"I just left something in my cart. This goes through the whole pipeline. First the **rules** check my limits. Then the **AI** picks an offer and writes the message. Then the **same rule code checks the AI's answer** before anything is sent. If the AI fails or is slow, the rules decide instead, so the bot is never silent."

"And every decision explains itself: why me, why this offer, which offers were rejected, which rules were checked, and whether the AI or the rules decided."

**Proof on screen:** the "Why this?" explanation.

---

## Scene 6 · A rule stops an offer (2:45 – 3:05)
**Show:** `/simulate purchase` → `/simulate cart`.

**Say:**
"I just bought something, so there's a rule: no discount for 48 hours after a purchase. The bot doesn't stay silent; it tells me why. Blocked decisions are logged too."

**Proof on screen:** the blocked reply with its reason.

---

## Scene 7 · Automation: offers sent by themselves (3:05 – 4:00) ⭐
**Show:** Overview → **Automations** card → **Personal picks** → **▶ Run now**.

**Say:**
"Offers don't only happen when a customer does something. Twice a day, at 11 and 6, the engine looks at every customer's profile (what they shop for most, their type, how likely an offer is to change their mind) and sends each one a personal pick. I'll press Run now so you can watch."

**Show:** the **run report** that opens.

"Here's the report. Every customer, their top category, the offer they got or why they got nothing, and whether the AI or the rules decided. Look at the offer mix: different people, different offers. Some got nothing on purpose, because they'd buy anyway."

**Show:** your **phone / Telegram DM**: your personal pick arrives.
**Show:** the **Customer Lab group**: "🎯 Personal pick" cards appear, and the shopper bots react (claim, ignore, "why me?").

"These ten are our lab customers. Each one gets a different offer, and they react in character."

**Show:** back to Overview: **Sent today**, **Budget used** and the margin card's **"Today: ₹… kept · ₹… spent"** line have changed.

"And the dashboard updates: offers sent today, money spent, and the margin we kept by *not* sending offers."

**Proof on screen:** run report rows; real DM on the phone; Lab group cards; changed Overview numbers.

---

## Scene 8 · Ten personas, ten answers (4:00 – 4:30) (optional if Scene 7 already showed the Lab)
**Show:** Lab group → `/lab@navpreet_offers_bot run 3`.

**Say:**
"The VIP gets early access, never a discount. The deal hunter gets a small discount with a minimum basket. The customer who gets annoyed by offers gets nothing. Personal, and inside the rules."

---

## Scene 9 · Playground: safe testing (4:30 – 5:05)
**Show:** **Playground** → **Cart abandoner** quick-pick → Run → toggle **Force LLM failure** → Run again.

**Say:**
"Marketers can test any customer without sending anything. Here's the Decision Pipeline: pre-gate, policy, agent, validator, sent. Each step is ticked or crossed. Now I force the AI to fail: the rules fallback decides, and it's checked by the same rules. The AI can fail; the customer still gets a correct answer."

**Proof on screen:** Pipeline Lens ✓/✗; "Rules fallback" badge on the second run.

---

## Scene 10 · Marketers set the rules (5:05 – 5:30)
**Show:** **Rules** → Persona → Deal hunter "at most **10%**" → change to **8%** → read the impact preview → **don't save** (or revert).

**Say:**
"Rules are plain sentences, not code. If I change 10% to 8%, before saving I see how many customers it affects and how much budget changes. Every save is a version I can undo in one click."

---

## Scene 11 · Every decision is recorded (5:30 – 5:50)
**Show:** **Decisions** → filter **Blocked** → open one → open an AI one.

**Say:**
"Every decision is logged: sent, held back, blocked or no offer, with the rule that stopped it, the AI's steps and timings. Nothing is hidden."

---

## Scene 12 · The proof: ₹91,760 and ₹14,916 (5:50 – 6:40) ⭐
**Show:** **Experiments** → **12 months**.

**Say:**
"So does it make money? This number is **measured, not counted**. For each campaign we compare the customers who got the offer with the random 10% who didn't. Extra buyers × the usual basket size = extra money the offers caused. Over the last 12 months, that's **₹91,760**."

**Show:** **ROI by offer type**.
"It's honest enough to show a loss too. One campaign gave free shipping to everyone. Those people actually bought *less* than the group who got nothing, and it lost about ₹24,000 of profit. That loss is exactly why targeting matters."

**Show:** Overview → the margin card.
"And **₹14,916** is margin saved. Some coupons go to people who would have bought anyway, and the control group tells us how many. Simple example: 100 coupons of ₹100, and 30 of those people would have bought anyway. ₹3,000 wasted. Our targeting avoids that waste."

**Optional proof (strong):** Neon → SQL Editor → run the read-only query that recomputes ₹91,760 from raw `campaign_history` rows:
"Here's the raw table and the same formula in plain SQL. It gives the same number as the dashboard."

---

## Scene 13 · Festivals and respect (6:40 – 7:00)
**Show:** **Festivals** page.

**Say:**
"The engine knows the festival calendar: Karwa Chauth, Dhanteras, Diwali, with budget per phase. We never guess religion from a name. Festival greetings only go to people who chose them, and the text comes from our table, never from the AI."

---

## Scene 14 · Close (7:00 – 7:15)
**Show:** Overview.

**Say:**
"So: realistic data, campaigns with control groups, a model that learns who an offer really helps, every offer checked by rules, offers sent automatically, and the money proven. **Rules set the limits, AI personalises inside them, and we only pay people when it changes what they do.** That's Holdout."

---

## 3-minute short cut
1 (problem) → 4 (`/start` card) → 5 (Why this?) → **7 (automation)** → 12 (₹91,760, free-shipping loss, ₹14,916) → 14 (close).

---

## Easy answers if someone asks after the video
| Question | Simple answer |
|---|---|
| Is the data real? | No: the rules require synthetic data. It's a year of simulated shopping checked against real benchmarks, and the method works the same on real data. |
| Why didn't ₹91,760 change after sending offers? | It's measured against control groups. Live offers to real people have no control group yet, so they can't be counted fairly. What changes live is today's spend and margin kept. |
| What if the AI is wrong? | The same rule code checks every AI answer. If it fails, the rules decide. |
| When does the number change? | It's a rolling 12 months. The next change is around 25 Nov, when Black Friday 2025 leaves the window. |
| Could this be a real product? | Yes. The decision brain is ready; a real shop needs a store connector, real coupons, WhatsApp and privacy consent. |
