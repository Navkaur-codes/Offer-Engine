# handoff-main.md: how the Main / Integrator session works (read this first)

> Written on 25 Oct 2026 by the previous main session when its context ran out. Read it together with
> `CLAUDE.md`, `docs/claude-progressive.md`, `docs/sessions.md`, the last ~5 entries of `docs/progress.md`,
> `docs/detective.md` and `docs/contracts.md`.

## Who you are
- You are the **Main / Integrator** session, working in `D:\hackathon-2` on branch `main`.
- You own the paths in `CLAUDE.md §4`: `main.py`, `config.py`, `db.py`, `models.py`, `contracts.py`, `ports.py`, `stubs.py`, `decision_store.py`, `runtime.py`, `api/`, `scheduler/`, `tests/api/`, `tests/conftest.py`, `docs/**`, deploy files and the README.
- You run the **gates**: merge each session's branch, fix integration, test, deploy, verify live, then write the docs for the next phase.
- You answer **contract change requests**.
- **The user does every git write.**
  - You give exact commands; the user runs them and replies `committed` / `merged` / `conflict` / `done`.
  - Read-only git is fine for you (`status`, `log`, `fetch`, `merge-tree`, `rev-parse`).

## The 4 parallel sessions (message them with SendMessage, using the session ID)
| Session | Folder | Branch | Session ID |
|---|---|---|---|
| A · Data & Scoring | `D:\offer-engine-A` | `feat/data-scoring` | `local_8a761235-fe1a-4d20-829d-c6e36ec6c31e` |
| B · Decision Core | `D:\offer-engine-B` | `feat/decision-core` | `local_16566f17-60b0-489e-b6e2-3fbd321db544` |
| C · Telegram + Lab | `D:\offer-engine-C` | `feat/telegram-lab` | `local_57489669-b2f7-4100-83c8-dd330c45eae2` |
| D · Dashboard | `D:\offer-engine-D` | `feat/dashboard` | `local_eb9c97f7-59e9-43fe-9f8f-2cd5f0d3235c` |

- They are git worktrees of the same repo and share the venv `D:\hackathon-2\.venv`.
- **Phase prompts:** sent by SendMessage, each with folder + branch + the git rule + the END OF SESSION routine. Use `docs/prompts.md` as the base and add current specifics.
- **Before every phase:** the user fast-forwards the four folders to `main`:
  - `git -C D:/offer-engine-X merge --ff-only main`
  - then `git push origin feat/data-scoring feat/decision-core feat/telegram-lab feat/dashboard`

## How a gate is run (what worked)
1. **Pre-check (read-only):**
   - every branch is committed and pushed (`git rev-parse origin/<b>`);
   - boundaries are respected (`git diff --name-only main...<b>` shows only the session's owned paths and `docs/progress.md` / `docs/sessions.md`);
   - simulate the merges: `git merge-tree --write-tree --name-only main <b>`.
2. **Merges, one at a time, in order A → B → C → D:**
   - the user runs `git merge --no-ff feat/<x> -m "merge: Session X phase N (…)"`;
   - conflicts are almost always only `docs/progress.md` / `docs/sessions.md`. Resolve by **keeping every entry**:
     - remove the markers;
     - keep the newest row for each session in the board (update it to "Phase N done" with its hashes);
     - append both log entries.
   - Then run the full test suite **before** the user commits (`git add <files>` + `git commit --no-edit`), so every merge commit is green.
3. **Integration fixes:** tests written against stubs break when the real modules merge. `backend/tests/conftest.py` pins each test folder's *foreign* ports to stubs; extend it rather than editing the sessions' tests. Stub-behaviour tests call `stubs.*` directly.
4. **Tests:**
   - from `D:\hackathon-2\backend`: `../.venv/Scripts/python -m pytest -q` and `-m ruff check .`
   - frontend: `cd frontend && npm ci && npm run lint && npm run build`
5. **Smoke test** on a scratch SQLite DB:
   - `DATABASE_URL=sqlite:///<scratchpad>/x.db python -m app.data.seed --customers 500 --seed 7`;
   - then call `ports.decide` for a few customers and triggers: check statuses, explanations, kill switch, onboarding (`ports.create_profile_from_answers`).
   - Set `PYTHONIOENCODING=utf-8` (₹ breaks the Windows console).
   - When running uvicorn locally, start it from a folder **without** `.env` (`--app-dir D:/hackathon-2/backend`), or the production bot token is picked up.
6. **Deploy:**
   - the user runs `git push origin main`, and Render auto-deploys in about 3–5 min;
   - poll `GET https://offer-engine-n4jx.onrender.com/health` until the version or ports change;
   - check live API endpoints, then have the user test the live bot `@navpreet_offers_bot` on their phone;
   - if it errors, ask for the Render log line (`handler error … <Type>`) and the step.
7. **Docs:**
   - append a GATE-N entry to `progress.md` and update the version/phase tables;
   - add a `sessions.md` health-log row and update the board;
   - rewrite `claude-progressive.md` for the next phase;
   - give one 📌 checkpoint for the docs, then the fast-forward commands for the 4 folders;
   - send the next phase prompts **only when the user says so**.

## Style the user expects
- Short status first, then numbered steps, with every shell command in its own ```bash block (one command per block).
- A 📌 COMMIT CHECKPOINT block in the exact format of `CLAUDE.md §5a` (Folder, Branch, Files, Run).
- Verify things yourself (git state, tests, live endpoints) before claiming them; be honest about what wasn't checked.
- Never print secrets. To check `.env` values, read them in Python and print only shapes or booleans; mask tokens with a sed regex.
- Ask before changing already-committed behaviour ("this changes X from commit Y because…").

## Where things stand (25 Oct, Sun)
- `main` = `d7221c6` (Phase 3 started). Live: Render `https://offer-engine-n4jx.onrender.com` (API v0.3, contracts v1.1), Neon Postgres (about 1,500 customers seeded with the A1 generator), and the scheduler running (`/api/scheduler`).
- **Phase 3 is done in all four sessions, committed and pushed** (A also has a 1-line `progress.md` edit to commit):
  - **A:** `dad6a5a` (uplift T-learner + impact, the no-offer fix), `7cffbcd` (realism + experiments).
  - **B:** `36e0313` (zero-cost ≥ 0 + welcome perk: NO_OFFER 82% → 11%), `4d46263` (Groq single-call agent, `agent/budget.py`, read-only tools, top-5 batch, message validators), `272e397` docs.
  - **C:** `fe3e883` (Customer Lab: 10 customers `C900001–C900010` voiced round-robin by 4 "Lab Shopper" bots, `/lab here|run|who|persona|date|reset`), `a721d2b` docs.
  - **D:** `82ada66` (real API, v1.1, Automations tile), `f0fa291` (Rules editor), `59015a5` (Customers page), `449e48b` docs.

## GATE-3 to-do (next job)
1. Pre-check, then merge A → B → C → D as above. Expect docs conflicts, and maybe stub-related test failures that need the conftest.
2. **Groq models:** the user's key has **no Llama models**. Change the `config.py` defaults to `groq_model_agent="openai/gpt-oss-120b"` and `groq_model_fast="openai/gpt-oss-20b"`, update `.env.example` and `CLAUDE.md §8`, and have the user set `GROQ_MODEL_AGENT` / `GROQ_MODEL_FAST` on Render.
3. **CCR-B1 (accept):**
   - add ports `llm_budget_status` → `app.agent.budget.status` and `decide_batch` → `app.agent.harness.decide_batch` (stubs too);
   - show the budget in `/health`;
   - use `decide_batch` in `api/customers.py` campaign dry-run;
   - update `contracts.md §3`.
4. **CR-C1 (accept):**
   - `models.CustomerBotRow`: make `customer_id` the primary key and `username` a plain indexed column;
   - Neon already has `customer_bots` with `username` as PK, so add an idempotent migration in `db.py` (e.g. drop and recreate `customer_bots` if its PK is `username`; C rebuilds Lab rows every round);
   - tell A that its seed must not delete Lab customers (`C900…`) — read C's note in `sessions.md` (CR-C1 text).
5. **Reseed Neon** after merging (A's generator now writes response-type traces the uplift model needs):
   - the user runs, from `D:\hackathon-2\backend` in PowerShell: `$env:DATABASE_URL="<neon url>"`, then `..\.venv\Scripts\python -m app.data.seed --customers 1500 --seed 42`, then `Remove-Item Env:DATABASE_URL`;
   - Neon free tier is 0.5 GB, so keep it at about 1,500 customers.
6. **Render env vars to confirm:** `ADMIN_TELEGRAM_IDS` (the user's ID), `CUSTOMER_BOT_TOKENS` (**one-line** JSON `[{"token":"…"},…]`, copied from `D:\offer-engine-C\.env`), `GROQ_API_KEY`, and the two gpt-oss model IDs.
7. **Vercel** (dashboard):
   - New Project → import `Navkaur-codes/Offer-Engine`, root directory `frontend`, framework Vite;
   - env `VITE_API_URL=https://offer-engine-n4jx.onrender.com`, `VITE_USE_MOCKS=0`;
   - deploy;
   - then set Render `CORS_ORIGINS=http://localhost:5173,https://<vercel-domain>`.
8. **Live checks:**
   - `/start`, `/simulate cart`, `/why` give real offers, not "No offer";
   - in the Customer Lab group: `/lab here`, then `/lab run 5` on the production bot;
   - the dashboard on Vercel shows real decisions, the Rules editor saves with the passcode, and Customers loads.
9. Docs for Phase 4: Phase 4 tasks are in `context-1..4.md`, plus the README and the demo script (`prompts.md` MAIN-README). The freeze is **Mon 26 Oct 18:00**; submit by **Tue 10:00**.

## Known gotchas
- Postgres is stricter than SQLite (detective **T29**): BIGINT for Telegram IDs (fixed), timezone-aware vs naive datetimes (`decision_store.aware()`), JSON queries.
- Never run `--polling` with the production token, because it deletes the webhook. C uses `@navpreet_offers_dev_bot`.
- `.env` values must be on one line.
- The Lab uses **4 bots for 10 customers**, so code must work with 1–10 bots.
- Real Telegram users get `is_holdout=False`.
- Quiet hours apply only to proactive sends (`runtime.quiet_hours_apply`).
