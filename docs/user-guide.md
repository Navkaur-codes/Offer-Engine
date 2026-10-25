# User guide

Two audiences: **shoppers** who use the Telegram bot, and **marketers** who run Holdout from the dashboard. Everything is a student demo: every customer, offer and coupon is synthetic, and nothing can be bought.

---

## Part 1 · Shoppers: the Telegram bot

Open [@navpreet_offers_bot](https://t.me/navpreet_offers_bot) and press **Start**.

### Getting started
1. `/start` shows a short consent note.
2. Answer three taps: the **categories** you like, **how often** you shop, and whether you prefer **deals or quality**.
3. Optionally choose festival greetings you'd like (for example Diwali or Karwa Chauth). Greetings are only ever sent if you choose them.
4. Holdout builds your profile and decides a **welcome perk**, which arrives as an offer card.

### Pretend to shop: `/simulate`
Each command writes realistic shopping events for you and runs the full decision engine, so you can watch it decide.

| Command | What it pretends | What usually happens |
|---|---|---|
| `/simulate cart` (or `cart fashion`) | you added an item and left it 35 minutes ago | a nudge, free shipping or a small discount, if one pays for itself |
| `/simulate browse beauty` | you looked at several items | an early-access or category offer |
| `/simulate purchase` | you bought your cart | no offers with a discount for 2 days, by design |
| `/simulate inactive 60` | you've been away 60 days | you may move to "at risk", and a win-back may follow |
| `/simulate points_expiry` | your points expire soon | a points reminder |
| `/simulate festival diwali` | a festival moment | a festival-phase offer (greeting only if you opted in) |
| `/simulate payday` | it's payday | a payday offer |
| `/simulate persona deal_hunter` | switch your persona | compare how decisions change |

Sending `/simulate` with no arguments shows a button menu.

### Offer cards and buttons
Offers arrive as a picture card (value, category, coupon code and expiry) with the details as the caption. The buttons:
- **✅ Claim:** you'd use it.
- **⏰ Remind me tonight:** a reminder at 19:00.
- **🙅 Not for me:** no offers in that category for 14 days.
- **❓ Why this?:** the plain-English reason.

### Other commands
| Command | Does |
|---|---|
| `/why` | explains the last decision: why you, why this offer, what else was considered and why it was rejected, which rules were checked, and whether the AI or the rules decided |
| `/offers` | your active coupons |
| `/history` | your recent decisions, including "no offer" and blocked ones |
| `/profile` | what Holdout knows about you, in plain words |
| `/pause` | no offers for a while; `/resume` starts them again |
| `/stop` | unsubscribe completely, immediately |
| `/help` | all commands |

### Why didn't I get an offer?
Holdout only sends an offer when it's likely to change what you do, and within the shop's limits. Common reasons, always shown in the reply or in `/why`:
- you recently bought something (no discounts for 2 days);
- you already received several offers this week, or still hold active coupons;
- none of the allowed offers is expected to pay for itself for you;
- it's night (21:00–09:00): proactive messages wait until morning, but replies to your own commands come straight away.

---

## Part 2 · Marketers: the dashboard

Open https://offer-engine-nu.vercel.app. Anyone can look around. To change anything (rules, kill switch, festivals, simulations), click the **🔒** icon in the top bar and enter the admin passcode. Every page starts with a one-line **"Why this page exists"** note, and **⌘K / Ctrl + K** opens the command palette.

### Top bar and sidebar
- **Kill switch** (sidebar dot, always visible): stops every send immediately.
- **Budget meter:** today's offer spend against the daily cap; discount caps shrink above 80%.
- **AI status:** a "degraded AI" chip appears when the daily AI budget moves to the smaller model or to rules only.
- **Upcoming moments:** the next festival and its countdown.
- **Bot link and QR code**, and light/dark mode.

### Pages
| Page | Use it to |
|---|---|
| **Overview** | see in 10 seconds whether offers make money that wouldn't have come anyway. The orange hero number is incremental revenue vs the holdout (last 12 months). Watch the live decision stream, the funnel, who decided (AI vs rules) and the margin protected |
| **Decisions** | audit any decision. Filter by status, decided by, policy, trigger, festival or search. Click a row for the **Pipeline Lens** (Pre-gate → Policy → Agent → Validator → Sent), the explanation, each rule ✓/✗, the AI's tool calls and a preview of the Telegram card. Filters live in the URL, so you can share a view |
| **Rules** | change limits safely. Each rule is a sentence; click a number, type a new value and the **impact preview** shows how many customers and how much budget it affects. Save creates a new version; **History** shows every version with one-click revert. Global hard limits can't be switched off |
| **Customers** | explore segments: recency × value scatter by policy, search and filters. Open a customer for their scores in plain words, timeline and decisions, and use **Run decision now** (a dry run) or **Simulate trigger** (a real decision) |
| **Experiments** | prove the value: treated vs holdout, incremental revenue and profit, uplift by policy, ROI by offer type, Qini curve and festival lift, each with a one-sentence takeaway. Pick 30 days, 90 days or 12 months |
| **Festivals** | plan festival moments: phase calendar, per-phase strategy and budget, hero categories and the greeting preview (opt-in only) |
| **Realism** | check the synthetic data against real-world benchmarks (each shows its target band and ✓/✗) |
| **Playground** | try anything without sending: choose a customer (or a quick pick like "Cart abandoner"), a trigger and optionally a date, then **Run** and read each step. Turn on **force LLM failure** to watch the rules fallback decide safely |
| **Campaign dry-run** (⌘K or Customers) | pick a policy or festival and a budget to see who would get what, the cost, what was blocked and why |

### Typical marketer flow
1. **Overview:** is the engine creating incremental value today?
2. **Decisions:** filter "Blocked" to see which rules stop the most offers.
3. **Rules:** loosen or tighten one number, read the impact preview, save.
4. **Playground:** check a few customers under the new rule.
5. **Experiments**, a few days later: did the change pay off? Revert from History if not.

### Status words you'll see
| Status | Meaning |
|---|---|
| **Sent** | the offer passed every rule and went out |
| **Queued** | a proactive offer that came due at night; it's re-decided at 09:05 |
| **Held out** | the customer is in the 10% holdout: decided but deliberately not sent, so we can measure what offers cause |
| **No offer** | nothing allowed was worth sending (for example a sure-thing or sleeping dog), or a purchase was too recent |
| **Blocked** | a limit, the kill switch, `/stop` or `/pause` stopped it |
| **Dry run** | Playground or campaign preview; never stored or sent |

| Decided by | Meaning |
|---|---|
| **AI agent** | the AI chose and worded the offer, and the rules re-checked it |
| **AI agent (retry)** | the first answer broke a rule; the corrected second one passed |
| **Rules fallback** | the AI was unavailable, slow, over budget or declined a profitable offer, so the deterministic rules decided |
| **Pre-gate** | stopped before any AI call |
