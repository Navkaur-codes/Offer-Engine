# claude-progressive.md: current phase instructions

> This file is **rewritten by the main session before every phase**. It is imported by the root `CLAUDE.md`, so it applies to every prompt.
> Permanent rules stay in `CLAUDE.md`. This file only holds *what is true right now*.
> Keep it under 80 lines. Past versions of this file are summarised in `docs/progress.md`.

---

## Now
- **Version:** v1.0, **final. The project is closed (27 Oct 2026).** Only an emergency fix to keep the live demo working is allowed; anything else raises detective T22.
- **Final build:** `main` with the Polish batch (`claude/polish-2d7333`: personal picks automation, run report, `/api/today`, voiceover script, refreshed README and 2-page summary). 369 backend tests pass, ruff clean; frontend lint + build ✓. Every port is real (26).
- **Live:**
  - API https://offer-engine-n4jx.onrender.com (v1.0, contracts v1.1)
  - dashboard https://offer-engine-nu.vercel.app
  - bot `@navpreet_offers_bot` (QR in the README and the dashboard top bar)
  - Neon with ~1,500 customers; Customer Lab running in the group
- **Live numbers (12 months, 26 Oct):** +₹91,760 incremental revenue, about ₹1.7k profit (₹1,722), ₹14,916 margin saved. Measured against control groups; they don't change when offers are sent. Next change around 25 Nov 2026 (Black Friday 2025 leaves the window).
- **Automation:** personal picks at 11:00 and 18:00 IST for every Telegram and Lab customer, plus Run now on Overview → Automations. Each run uses one of each Lab customer's weekly offers.

## ⚠️ Judging settings on production (data, not code)
- Rules → Global: `G_FREQ` min gap **0 days** (was 2) and weekly cap **10** (was 3); `G_ONE_COUPON` **2** (was 1).
- All other limits are unchanged (48 h no-discount after purchase, quiet hours, margin guard, budget, caps).
- **After judging, revert all three under History:** weekly cap 10 → 3, gap 0 → 2 days, active coupons 2 → 1. Never revert them silently before then.

## Open items (after judging)
- Revert the three judging settings above.
- Keep Render, Vercel and cron-job.org up until judging is complete; then the bot may be stopped.
- Not done, by choice: new users answering "monthly + balanced" become `at_risk` and may get no welcome offer (44/48 answer combinations get one). Receipt panel, numbered sidebar flow, spending-profile line and festival campaign card were proposed but not built.

## Rules (still binding)
- Any emergency fix gets a regression test.
- Notes in `sessions.md §7` stay binding (festival keys without the year; offer params `pct`, `amount`, `min_basket`, `multiplier`, `category`; decisions only via `decision_store`; quiet hours for proactive sends only).
- Groq models `openai/gpt-oss-120b` / `openai/gpt-oss-20b`, only via `agent/budget.py`; free-tier TPM is ~3 agent decisions a minute, so 429s fall back to rules by design.
- **Never** `--polling` with the production token. In the Lab group, address the prod bot as `/lab@navpreet_offers_bot`; end any `/lab date` with `/lab date off`.
- No re-seed of Neon from now on unless a fix needs it (it changes the live Experiments numbers and screenshots).
- 📌 Give a checkpoint after every fix. The user does every git write.

## Known issues
- Uplift targeting is noisy (~80% of hidden types identifiable); the 90-day Experiments window holds one campaign with 47 controls.
- `/api/customers` policy filter scans 600 rows, so counts show "N+".
- Real Telegram users get `is_holdout=False`; synthetic customers keep the 10% holdout.

## Worktree folders
| Session | Folder | Branch |
|---|---|---|
| Main | `D:\hackathon-2` | `main` |
| A | `D:\offer-engine-A` | `feat/data-scoring` |
| B | `D:\offer-engine-B` | `feat/decision-core` |
| C | `D:\offer-engine-C` | `feat/telegram-lab` |
| D | `D:\offer-engine-D` | `feat/dashboard` |
