# 🕵️ detective.md: the Project Detective

> **Purpose:** stop us from building common, generic features that waste time or cost points.
> Claude checks every feature request against this file (see `CLAUDE.md §6`). On a match it **interrupts** with a ⚠️ DETECTIVE block and waits for your answer.
> Add new traps whenever you discover one. Never delete a trap; mark it "retired" with a reason instead.

## The 5 gate questions (ask before *any* feature)
1. **Judging:** which judging criterion does it raise (core, data realism, usability, design, advanced, relevance)? If none, it's a trap.
2. **Visibility:** will a judge *see* it within a 5-minute demo, in the bot or dashboard? If not, it is low priority unless it supports a non-negotiable.
3. **Safety:** does it weaken a non-negotiable (validator, fallback, secrets, consent, cultural safety)? If yes, **stop**.
4. **Ownership:** is it inside your session's owned paths? If not, **stop** and route it through the main session.
5. **Time:** can it be finished and tested before the next phase gate? Is it before the freeze (Mon 26 Oct, 18:00)? If not, cut it or shrink it.

## Trap list
| ID | Trap (red flag) | Why it hurts | Do instead |
|---|---|---|---|
| T01 | **Building a store**: product pages, cart UI, checkout, payments | The brief says there is no store to build. It eats days and earns zero points | Simulate shopping with `/simulate` commands and Lab events |
| T02 | **Generic chatbot**: "ask the bot anything", free-form LLM chat with customers | Off-brief, gives unpredictable output, and invites prompt injection | Use structured commands and buttons. The LLM only writes offer messages and explanations |
| T03 | **LLM decides alone**: sending whatever the model returns | Breaks the core judging criterion ("every AI choice must be checked") | Use the harness, then `evaluate()`, then retry, then the fallback. Always |
| T04 | **Rules hard-coded** as `if persona == "vip"` in code | Marketers can't adjust them, which fails usability | Store rules as DB rows with `describe()`, editable in the Rules page |
| T05 | **Discount everyone / blanket 20% off** | This is exactly the lost margin the brief warns about. It fails relevance | Use uplift, sure-thing protection, the escalation ladder, and zero-cost offers first |
| T06 | **Generic or recycled look:** blue/green gradient "AI" UI, glassmorphism, sparkles, neon; **beige/paper/skin-tone palettes (already used in Hackathon 1)**; regional or cultural decoration in the UI | Looks like every other entry, or like your own previous project, and the design score drops | Use the **Signal** tokens in `CLAUDE.md §7`: cool monochrome, one orange accent, dark sidebar, Pipeline Lens |
| T07 | **Vanity dashboard**: lots of charts, no actions | Marketers can't *do* anything with it, which hurts usability | Every page needs one primary action, and the top bar has the 80% actions |
| T08 | **Pie/donut charts, 3D charts, gauges** | Hard to read; fails "results easy to read" | Use bars, lines, tables with sparklines, and KPI strips with ▲▼ |
| T09 | **Login/auth system**: signup, OAuth, roles | Not judged, takes a day | One `ADMIN_PASSCODE` header for writes; public read-only |
| T10 | **Microservices / Kubernetes / Kafka / Redis queues** | Over-engineering, and free hosting breaks it | One FastAPI service with APScheduler in-process |
| T11 | **Bot polling in production / multiple processes** | Webhook conflicts, and it dies when Render sleeps | Webhook in prod plus the cron-job.org ping. Use polling only locally or as the backup |
| T12 | **Uniform-random data**: `random.randint` for spend, independent columns | Fails data realism immediately | Day-by-day simulation, Pareto/lognormal distributions, funnels, seasonality, churn hazard |
| T13 | **Real data / scraped profiles / real phone numbers** | Violates the brief and privacy | Faker `en_IN` plus our own generator |
| T14 | **Secrets in code, commits or screenshots** | Disqualification risk and a hijacked bot | `.env` plus host env vars, gitleaks, `.env.example` with names only |
| T15 | **No fallback when Groq rate-limits** | The bot goes silent during judging | Fallback always on, and the token bucket limits calls |
| T16 | **Rules a marketer can't read**: JSON editors, regex fields | Fails usability ("without help") | Plain-English sentence cards with inline number inputs and an impact preview |
| T17 | **Inferring religion/ethnicity from names** for festival offers | Offensive and a reputational risk | Opt-in festival preferences; neutral "festive season" by default |
| T18 | **LLM-invented facts**: prices, stock, deadlines, greetings | Broken promises and validator failures | Every fact comes from a tool. The validator checks numbers and dates in the text |
| T19 | **Spamming classmates**: many offers per day, sends at night | People block the bot, delivery fails, and judges see it | Frequency cap, quiet hours, and the Lab group for heavy demos |
| T20 | **Testing only on yourself** | Hidden onboarding bugs; no real outcome data | Share the bot on day 1 and run a test round with 10 or more classmates on Mon |
| T21 | **Editing another session's folder / changing contracts directly** | Merge conflicts and broken integration | Use `ports.py` and stubs, and add a contract change request in `sessions.md` |
| T22 | **New features after the freeze (Mon 18:00)** | Last-night bugs can kill the demo | Fix, polish and write docs only |
| T23 | **Building ML that nobody sees**: deep learning, complex tuning | Time sink, invisible to judges | A simple T-learner and logistic regression, with results shown on Experiments and Realism |
| T24 | **Fancy features over a broken core**: Hinglish, images, ⌘K before `/simulate cart` works end-to-end | You look advanced with nothing working underneath | Build MUST items first (PLAN §2), then SHOULD, then WOW |
| T25 | **Agent can write data**: tools that update the DB or send messages | One injection away from abuse | Read-only tools. The harness writes |
| T26 | **One giant LLM prompt per batch of 5,000 customers** | Free-tier rate limits, plus cost and latency | Use the agent for live triggers and the Lab. Batch campaigns use the fallback scorer, with the agent only on the top-N |
| T27 | **Undocumented behaviour**: features missing from the README | Judges won't find them | README "Demo in 5 minutes" section and a "Why this page" note on each page |
| T28 | **Customer bots trying to receive DMs** | Telegram blocks bot-to-bot messages | The backend orchestrates the Lab group (PLAN §5 Customer Lab) |

## Time-based alarms (Claude raises these on its own)
- **Thu 22 Oct, 23:59:** if the bot isn't deployed and the link isn't shared, that's an 🚨 alarm and the top priority.
- **Fri 23 Oct, 23:59:** if `/simulate cart` doesn't work end-to-end (decision → validator → Telegram → log), the agent and lab work pause until it does.
- **Sat 24 Oct, 23:59:** if the dashboard doesn't show real decisions from the API, focus moves to integration, not new pages.
- **Mon 26 Oct, 18:00:** **feature freeze**. Every new-feature request raises T22.
- **Tue 27 Oct, 10:00:** submit no later than this, leaving a 2-hour buffer.

## Detective overrides log
Record each time you chose to proceed despite a warning. One line each: date, trap ID, reason.
- _none yet_
