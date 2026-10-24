# context-3.md: Session C, Telegram Bot + Customer Lab

**Branch:** `feat/telegram-lab`
**Worktree:** its own worktree
**Read first:** `CLAUDE.md`, `docs/claude-progressive.md`, `docs/contracts.md`, `docs/detective.md`, `docs/PLAN.md §5, §4b`

## Mission
Make offers **reach real classmates** with clear, attractive messages. Turn the bot into a **simulation console** (`/simulate …`, `/why`). Build the **Customer Lab**, where a few "Lab Shopper" bots act out 10 personas in a Telegram group and the Offer bot responds live.
This session covers the **core functionality (delivery)** and **design (messages)** criteria and is the centrepiece of the demo.

## Owned paths
`backend/app/bot/`, `backend/app/lab/`, `backend/tests/bot/`

## Never touch
`data/`, `scoring/`, `rules/`, `agent/`, `frontend/`, `contracts.py`, `models.py`, `api/`, `main.py`.
The main session mounts your webhook route.

## Consumes
- Through `app.ports`: `decide()`, `explain()`, `build_profile()`, `create_profile_from_answers()`, `get_context()`, `digest.daily()`. These are stubbed until Sessions A and B merge.
- Also `app.db`, `app.models`, `app.config`.

## Produces
- `bot.app.build_application()`, the python-telegram-bot v21 `Application`.
  - Main mounts it on `POST /telegram/webhook/{TELEGRAM_WEBHOOK_SECRET}`.
  - `python -m app.bot --polling` runs it locally.
- `bot.sender.deliver(decision, channel)`
- `lab.runner.run_rounds(n)`

---

## Phase 1 (v0.2): Onboarding, profile, first offer card (stub `decide`)
**Tasks:**
1. `bot/app.py`: application factory, handler registration, error handler (it logs and replies with a friendly message, and never crashes the webhook).
2. `bot/onboarding.py`, the `/start` flow, using inline buttons only:
   1. Consent: "This is a demo with synthetic offers; no real purchases."
   2. Favourite categories (multi-select).
   3. Shopping frequency.
   4. Deal vs. quality.
   5. **Optional festival greetings** (opt-in, multi-select: Diwali, Gurpurab, Lohri, Karwa Chauth, Christmas, "none"), which feeds the cultural-safety guardrail.
   - The flow then calls `create_profile_from_answers()` and then `decide(trigger="welcome")`, then `deliver()`.
3. `bot/render.py`: one function that turns a `Decision` into Telegram HTML:
   - bold headline;
   - two personal lines;
   - a value line such as `🎟 Free shipping · till 25 Oct`;
   - the coupon in `<code>`;
   - a muted footer: "Reply /why to see why you got this · /stop to opt out".
   - Inline buttons: ✅ Claim · ⏰ Remind me tonight · 🙅 Not for me · ❓ Why this?
   - NO_OFFER and BLOCKED decisions get their own short, friendly messages.
4. `/profile` (persona, policy and key scores in plain words), `/help`, `/offers`, `/pause`, `/stop`. `/stop` sets `opted_out`, and the harness then blocks sends.

**Done when:**
- Running locally in polling mode: `/start` then the welcome offer card renders correctly on a phone, and the buttons respond.
- Tests use the PTB test utilities or mocked `Bot` calls.

## Phase 2 (v0.3): `/simulate` commands, buttons, `/why`
**Tasks:**
1. `bot/simulate.py`: each command below writes realistic events, refreshes the profile, calls `decide()` with the matching trigger, and calls `deliver()`. Each also replies with a one-line status first (e.g. "🧪 Simulated: added Cotton Kurta ₹1,450 to cart, 35 min ago").
   - `/simulate cart [category]`
   - `/simulate browse <category>`
   - `/simulate purchase`
   - `/simulate inactive [days]`
   - `/simulate points_expiry`
   - `/simulate festival <name> [phase]`
   - `/simulate payday`
   - `/simulate persona <name>`
   - `/simulate` with no arguments shows a button menu.
2. Button callbacks:
   - **Claim** records `offer_claimed` and the outcome, and replies "Saved! Use code …".
   - **Remind me tonight** schedules a reminder at 19:00 IST through the job queue.
   - **Not for me** records a decline and suppresses that category for 14 days, using the Individual rule through a port, if available.
   - **Why this?** replies with `explanation.telegram_text`.
3. `/why`: the explanation of the last decision. `/history` lists the last 5 decisions, including blocked and no-offer ones, each with a one-line reason.
4. Rate-limit users to about 1 simulate per 10 s, and show friendly error copy.

**Done when:**
- `/simulate purchase` then `/simulate cart` replies "no offer, here's why (bought <48h ago)".
- `/simulate inactive 60` gives a win-back offer.
- All buttons are recorded in the DB.

## Phase 3 (v0.4): Customer Lab (10 customers voiced by 1–10 bots)
**Before starting:**
1. BotFather's rate limit stopped the user at **4 bots** (25 Oct). They are renamed **"Lab Shopper 1–4"** and voice all 10 Lab customers in rotation, so the design must work with **any number of bots from 1 to 10**. Ask for `CUSTOMER_BOT_TOKENS` in your worktree `.env` when you need it; never ask for tokens in chat.
2. There is **no** shadow channel, and `/lab here` auto-detects the group (items 5–6).
3. Also verify on the dev bot that `/simulate cart` → card → buttons → `/why` work against the **real** harness. It's merged now; until A3/B3 land, many results will be "No offer".
**Background:** a bot cannot DM another bot, and bots don't see each other's group messages. **The backend orchestrates everything**, and the customer bots only *send*.

**Tasks:**
1. `lab/registry.py`:
   - **10 fixed Lab customers** `C900001`–`C900010` in a constant `LAB_CUSTOMERS`, each with a name and persona:
     - Arjun · VIP, Priya · deal hunter, Gurpreet · at-risk, Simran · new user, Rohan · cart abandoner;
     - Aisha · window shopper, Vikram · high returner, Meera · sleeping dog, Karan · dormant, Neha · festive gifter.
   - Ensure they exist with `is_lab_bot=True` and matching history (reuse A's generator/onboarding; "sleeping dog" is a hidden response type on a fitting persona).
   - Load `CUSTOMER_BOT_TOKENS` as a JSON list. The minimal form is `[{"token": "..."}, ...]`. Extra keys (`customer_id`, `persona`) are allowed and ignored, so the old format still works.
   - **Assign customers to bots round-robin:** customer *i* → bot *i mod n*, so 4 bots voice 3/3/2/2 customers and 10 bots voice one each.
   - Never log a token. Store only the bot **username** (from `getMe`) in `customer_bots`. Each customer maps to the bot that voices them, and several rows per bot are fine.
   - With 0 tokens, `/lab run` replies "No Lab Shopper bots configured" and the Offer bot runs nothing.
2. `lab/scripts.py`: per-persona activity scripts that are realistic and festival-aware. Each step is an event plus a human line, e.g. "🛒 Priya added Silk Saree ₹3,499 to cart".
3. `lab/runner.py`: `run_rounds(n)`. For each round:
   1. Pick a **Lab customer** (rotate so every persona appears; don't repeat one before all 10 have had a turn), then the bot that voices them.
   2. That bot posts in the Lab group (`runtime.lab_group_chat_id()`). **Every post starts with who is acting**, e.g. `👤 Priya · Deal hunter`, then the activity line. The name line is what makes 4 shared voices read as 10 people.
   3. Write the event.
   4. `decide(trigger="lab")`.
   5. The Offer bot **replies to that message** and addresses the **customer by name** (not the bot), with the rendered card, or with "No offer for Arjun: VIP sure-thing, margin protected ₹X".
   6. The same bot answers **as that customer**, prefixed with the name ("Priya: Claimed ✅ …"), in character. A persona response model (hidden response type plus noise) decides claim, ignore, decline or ask "why?". The line is short, either from templates or the fast Groq model with a template fallback.
   7. Record the outcome.
   - Space messages 2–4 seconds apart so the conversation is readable and stays within Telegram limits.
4. Group commands (admin only):
   - `/lab run [n]`
   - `/lab persona <name> <state>`: force inactive, festival, etc., by **customer name** (Priya, Arjun…), since bots are shared.
   - `/lab who`: lists the 10 Lab customers and which Lab Shopper voices each.
   - `/lab date YYYY-MM-DD`: set `DEMO_TIME_OVERRIDE` through a port so you can time-travel to Dhanteras.
   - `/lab reset`
   - A reply of `/why` on an offer shows its explanation.
5. **`/lab here`** (admin only, in a group): saves that chat as the Lab group with `runtime.set_lab_group(chat_id, title)`, then replies "✅ This group is now the Customer Lab". No manual chat ID is needed; `LAB_GROUP_CHAT_ID` is only an optional override. `/lab run` in an unregistered group says "Type /lab here first".
   - **The shadow channel is removed** (24 Oct). The dashboard's live stream covers it.
6. **Quiet hours (24 Oct decision):** set `trigger_meta["initiated_by"] = "customer"` on `/start` welcome, `/simulate` and button-driven decisions, so the harness answers immediately at night. Lab rounds use `trigger="lab"` (also exempt).

**Done when:** `/lab run 5` in the real group produces 5 readable exchanges, with different personas getting visibly different treatment, including at least 1 "no offer, margin protected".

## Phase 4 (v1.0): Admin, polish, resilience
**Tasks:**
1. Admin commands (checked against `ADMIN_TELEGRAM_IDS`): `/summary` (today's digest), `/killswitch on|off`, `/campaign run <policy>` (small batches, respects caps), `/impersonate <customer_id>`.
2. Polish the copy for every message. Use emoji sparingly, keep the structure consistent, check rendering on Android and iOS, and handle long names.
3. Resilience:
   - catch Telegram 403 (user blocked the bot) and mark the customer as unreachable;
   - retry with backoff on 429/5xx;
   - make webhook handlers idempotent using `update_id` dedupe.
4. Optional: an offer card image (Pillow, Signal palette: graphite header, orange value, amber expiry chip), sent as a photo with the caption. Use text only if time is short.

## Stub strategy
Use `app.ports.decide`. Until Session B merges, it returns fixture Decisions from `app.stubs`. They are deterministic by input:
- policy `vip` (customer `C000003`) gives NO_OFFER;
- trigger `manual` gives BLOCKED;
- everything else gives SENT.

Build and test all rendering against these fixtures.

**Local testing bot (important):** never run `--polling` with the production Offer bot token. Polling deletes the live webhook on Render, so classmates stop getting replies.
- Create a separate **dev bot** in BotFather (e.g. `<name>_dev_bot`).
- Put its token in your worktree's own `.env`.
- `backend/app/bot/app.py` is the Phase-0 hello version. Replace it, keeping the `build_application()` name.

## Tests
```
pytest backend/tests/bot -q
```
Render snapshot tests: `Decision` fixture → expected HTML.

## Detective traps
T01, T02, T11, T19, T20, T28, T17.

## Handoff checklist
- [ ] Tests green, `ruff` clean, every finished task given to the user as a 📌 COMMIT CHECKPOINT, and the user confirmed it is pushed to `feat/telegram-lab`.
- [ ] Screenshots of the welcome card, cart nudge, `/why` and a Lab exchange saved to `docs/screenshots/`. This session may create that folder.
- [ ] `progress.md` entry and `sessions.md` row updated, including the BotFather setup steps the user must do manually.
