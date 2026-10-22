# claude-progressive.md: current phase instructions

> This file is **rewritten by the main session before every phase**. It is imported by the root `CLAUDE.md`, so it applies to every prompt.
> Permanent rules stay in `CLAUDE.md`. This file only holds *what is true right now*.
> Keep it under 80 lines. Past versions of this file are summarised in `docs/progress.md`.

---

## Now
- **Version:** v0.1 (Setup)
- **Phase:** 0, Foundation. Only the main session works; the parallel sessions have not started yet.
- **Date window:** Thu 22 Oct 2026
- **Next gate:** Phase-0 gate means the scaffold is committed on `main`, then sessions A–D start Phase 1.

## Goals of this phase (main session only)
1. Run `git init`, create the GitHub repo, and add `.gitignore` (`.env`, `.venv`, `node_modules`, `*.db`, `__pycache__`, `dist`).
2. Scaffold the folders from `docs/PLAN.md §10`. Add empty `__init__.py` files and `backend/pyproject.toml` with dependencies.
3. Write `backend/app/contracts.py` exactly as in `docs/contracts.md`.
4. Write `app/ports.py` and `app/stubs.py`, where the stubs return fixture data.
5. Write `app/config.py` with `now()` honouring `DEMO_TIME_OVERRIDE`.
6. Write `.env.example` with variable names only.
7. Make a minimal FastAPI app with `/health` and a bot `/start` that replies "hello". **Deploy it to Render, set the webhook, and share the bot link with classmates today.**
8. Make the first commit, then create the branches `feat/data-scoring`, `feat/decision-core`, `feat/telegram-lab` and `feat/dashboard`.

**Git (applies in every phase):** the user runs every git write command. In steps 1 and 8, Claude only gives the commands, and gives a 📌 checkpoint after each finished step.

## Temporary rules for this phase
- No feature logic yet: no rules, agent, generator or UI pages. Only the scaffold and contracts.
- Contracts can change freely in this phase. **After the Phase-0 gate they freeze**; changes then go through "Contract change requests" in `sessions.md`.

## Known issues / decisions pending
- Festival dates for 2026 must be checked against a panchang (Session A, Phase 1).
- BotFather setup still to do:
  - Create the Offer bot and 10 customer bots.
  - Disable privacy mode for the Offer bot in the Lab group.
  - Note the group chat ID.

## Contract version
`contracts v1` (draft, freezes at the Phase-0 gate)
