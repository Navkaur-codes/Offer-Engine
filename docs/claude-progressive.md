# claude-progressive.md: current phase instructions

> This file is **rewritten by the main session before every phase**. It is imported by the root `CLAUDE.md`, so it applies to every prompt.
> Permanent rules stay in `CLAUDE.md`. This file only holds *what is true right now*.
> Keep it under 80 lines. Past versions of this file are summarised in `docs/progress.md`.

---

## Now
- **Version:** v1.0 (target **Mon 26 Oct 18:00 = feature freeze**). Submit by **Tue 27 Oct 10:00**.
- **Phase:** 4, the last build phase. After the freeze: fixes, polish and docs only (detective T22).
- **GATE-3 passed (25 Oct).**
  - `main` has all Phase-3 merges plus B's fix `13a4cf4`; 279 backend tests pass and the frontend builds.
  - Production uses the **real Groq agent** (gpt-oss-120b → gpt-oss-20b → rules, via `agent/budget.py`).
  - The scratch smoke test shows 79% of decisions would send, mostly zero-cost offers.
- **Live:**
  - API https://offer-engine-n4jx.onrender.com (v0.4, contracts v1.1)
  - dashboard https://offer-engine-nu.vercel.app
  - bot `@navpreet_offers_bot`
  - Neon re-seeded with 1,500 customers
  - Customer Lab running in the group
- **Still stubs:** `rule_impact` and `daily_digest` (both are B's Phase 4 tasks). Check with `/health`.
- **Next gate:** GATE-4 = v1.0 at the freeze. Needs:
  - classmates getting offers;
  - every dashboard page on real data;
  - the README "Demo in 5 minutes";
  - a classmate test round done.

## 🔴 PRIORITY 0 for Phase 4
- **B:** the live Lab showed the agent choosing "no offer is worth its cost" for a cart abandoner, a new user and a deal hunter, where the fallback would have sent a zero-cost perk.
  - Make the agent prefer the best zero-cost allowed offer at profit ≥ 0.
  - It may pick no-offer only when nothing allowed pays for itself.
  - Ship this as its own checkpoint first.
- **A + C (CR-C1 follow-up):**
  - C writes one `CustomerBotRow` per Lab customer.
  - A's seed skips `is_lab_bot` customers and their rows, so a re-seed never wipes the Lab.

## Phase-4 goals (details in each context file)
- **A:** benchmarks comfortably in range, `docs/data-dictionary.md`, edge cases, seed < 2 min, profile < 50 ms.
- **B:** priority 0; then `agent/digest.py`, `rules/preview.py` (`impact`), profiling (fallback < 100 ms, agent p50 < 4 s).
- **C:** admin commands (`/summary`, `/killswitch`, `/campaign run`, `/impersonate`), copy polish, resilience (403, 429/5xx backoff, `update_id` dedupe). The card image is optional.
- **D:** Experiments (auto takeaways), Festivals, Realism (benchmark bands), Playground (step-by-step trace, the demo hero), campaign dry-run, code-splitting (bundle ~1 MB), screenshots for the README.
- **Main:**
  - README with "Demo in 5 minutes" and a demo script;
  - GATE-4;
  - keep Render/Vercel/cron-job.org healthy;
  - organise the classmate test round with the user.

## Temporary rules for this phase
- Notes in `sessions.md §7` are binding:
  - festival keys don't include the year;
  - offer params are `pct`, `amount`, `min_basket`, `multiplier`, `category`;
  - write decisions only via `decision_store`;
  - quiet hours apply to proactive sends only.
- Groq models are `openai/gpt-oss-120b` / `openai/gpt-oss-20b`. Real calls go only through `agent/budget.py`; keep test runs small (free-tier TPM is about 3 agent decisions a minute).
- Batches (campaigns, `/lab run` > 5) use `ports.decide_batch`, so the agent only handles the top 5 (T26).
- `tests/conftest.py` pins foreign ports to stubs in your unit tests; mark a test `@pytest.mark.real_ports` to opt out.
- **Never** run `--polling` with the production token. C uses the dev bot. In the Lab group, address the prod bot as `/lab@navpreet_offers_bot`.
- BIGINT for external IDs; test anything number- or time-heavy against Postgres semantics (T29).
- 📌 Give a checkpoint after every finished task. **No new features after Mon 18:00.**

## Known issues
- The bundle is ~1 MB; code-split by route (D).
- `/api/customers` policy filter scans 600 rows, so counts show "N+".
- `/lab date` moves the engine clock for the whole process (prod too); always end with `/lab date off`.
- Real Telegram users get `is_holdout=False`; synthetic customers keep the 10% holdout.

## Worktree folders
| Session | Folder | Branch |
|---|---|---|
| Main | `D:\hackathon-2` | `main` |
| A | `D:\offer-engine-A` | `feat/data-scoring` |
| B | `D:\offer-engine-B` | `feat/decision-core` |
| C | `D:\offer-engine-C` | `feat/telegram-lab` |
| D | `D:\offer-engine-D` | `feat/dashboard` |
