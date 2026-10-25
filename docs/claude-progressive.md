# claude-progressive.md: current phase instructions

> This file is **rewritten by the main session before every phase**. It is imported by the root `CLAUDE.md`, so it applies to every prompt.
> Permanent rules stay in `CLAUDE.md`. This file only holds *what is true right now*.
> Keep it under 80 lines. Past versions of this file are summarised in `docs/progress.md`.

---

## Now
- **Version:** v1.0. **Feature freeze: Mon 26 Oct 18:00.** Submit by **Tue 27 Oct 10:00** (deadline 12:00).
- **Phase:** post-GATE-4. **Fixes, polish and docs only.** Any new feature raises detective T22.
- **GATE-4 passed (25 Oct).**
  - `main` has all Phase-4 work and the GATE-4b fixes; 337 backend tests pass; frontend builds (289 kB main chunk).
  - Every port is real; `/health` lists none as stub.
- **Live:**
  - API https://offer-engine-n4jx.onrender.com (v1.0, contracts v1.1)
  - dashboard https://offer-engine-nu.vercel.app
  - bot `@navpreet_offers_bot`
  - Neon with ~1,500 customers; Customer Lab running in the group
- **Live numbers (12 months, 25 Oct):** +₹91,760 incremental revenue, +₹1,723 profit, ₹14,916 margin saved.

## ⚠️ Judging settings on production (data, not code)
- Rules → Global: `G_FREQ` min gap **0 days** (was 2) and weekly cap **10** (was 3); `G_ONE_COUPON` **2** (was 1). This way `/start` → `/simulate cart` gives an offer, and Lab customers capped by testing can receive offers again.
- All other limits are unchanged (48 h no-discount after purchase, quiet hours, margin guard, budget, caps).
- **Revert both under History after judging.** Never revert them silently before then.

## Open items
- **B:** the agent must not decline when an allowed candidate has positive expected profit; no-offer reasons must be deterministic (no LLM-invented rules). In progress.
- **User + Main:** classmate test round (share the bot link, collect outcomes); then SUBMIT (`prompts.md → SUBMIT`).
- **Main:** keep Render, Vercel and cron-job.org healthy; gitleaks on the full history before submission.

## Rules for this phase
- Only fixes that a live check or a classmate found, copy polish and docs. Each fix gets a regression test.
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
