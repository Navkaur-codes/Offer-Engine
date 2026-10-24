# prompts.md: copy-paste prompts for every session × phase × version

> **How to use:** open the right session and paste the block. Each prompt is self-contained.
> Order of the day: **MAIN-0 → (A1, B1, C1, D1 in parallel) → GATE-1 → (A2…D2) → GATE-2 → … → GATE-4 → SUBMIT.**
> Never paste a session's next phase before the main session has run that gate.
>
> **Git rule (CLAUDE.md §2.12 and §5a):** you make every commit, push and merge yourself. Sessions never do. When something is finished, a session stops and shows a **📌 COMMIT CHECKPOINT** block with the exact commands and folder. Run them, then reply `committed`. The session won't touch those files again until you do.

---

## Prompts that work in any session

### RESUME (paste when reopening any session)
```
Resume work. Read CLAUDE.md, docs/claude-progressive.md, my context file (docs/context/context-<N>.md),
docs/detective.md, and the last 3 entries of docs/progress.md plus my row in docs/sessions.md.
Tell me in 5 lines: current phase, what is done, what is left, any blocker. Then continue the next unfinished task.
```

### DETECTIVE CHECK (paste before starting a new idea)
```
Detective check: I want to <describe idea>. Run it through docs/detective.md (5 gate questions + trap list)
and give me the ⚠️ DETECTIVE verdict before writing any code.
```

### END OF SESSION (paste before closing any session)
```
Wrap up this session: run my tests and lint, append an entry to docs/progress.md using the template, update my
row in docs/sessions.md (phase, status, blockers, notes for other sessions, contract change requests), then give
me the final 📌 COMMIT CHECKPOINT (folder, branch, files, git add/commit/push commands) for everything not yet
committed. Do not run git write commands yourself. Show me the summary.
```

---

## MAIN SESSION

### MAIN-0: Step 0, foundation (v0.1, Thu)
```
We are in Phase 0 (see docs/claude-progressive.md). You are the MAIN / Integrator session.
Do Step 0 from docs/PLAN.md §11c exactly:
1. .gitignore (.env, .venv, node_modules, *.db, __pycache__, dist). Give me the commands to run git init,
   connect my GitHub repo (I'll tell you its URL) and make the first commit of the docs. I run them, not you.
2. Scaffold folders from PLAN §10 with __init__.py files; backend/pyproject.toml with all deps from CLAUDE.md §8 (+ dev: pytest, hypothesis, ruff).
3. backend/app/contracts.py mirroring docs/contracts.md §1–2 exactly (Pydantic v2).
4. backend/app/config.py (settings from env, now() honouring DEMO_TIME_OVERRIDE, Asia/Kolkata),
   db.py (SQLModel engine, SQLite default), models.py (tables for customers, products, events, orders,
   offers, rules, rule_versions, decisions, festivals, settings, customer_bots).
5. backend/app/ports.py + stubs.py: every function in contracts.md §3, routed to the real module if importable,
   else to a stub returning realistic fixtures (5 profiles, one per main policy; SENT/NO_OFFER/BLOCKED decisions).
6. .env.example with names only; minimal FastAPI main.py with /health; a tiny bot /start that replies hello,
   mounted at /telegram/webhook/{secret}; Dockerfile for Render.
   Give me a 📌 COMMIT CHECKPOINT after each of steps 3–6, and wait for "committed" each time.
7. Help me deploy: Render web service + env vars, setWebhook, cron-job.org ping. Then I share the bot link.
8. Give me the commands to create and push branches feat/data-scoring, feat/decision-core, feat/telegram-lab,
   feat/dashboard from main. I run them.
Then freeze contracts (v1), update sessions.md + progress.md, rewrite claude-progressive.md for Phase 1.
```

### GATE-N: phase gate (run after every phase; replace N)
```
Run phase gate GATE-<N>. Follow docs/sessions.md §3 checklist exactly:
check each session's "Done when" for Phase <N> in docs/context/context-1..4.md and that each branch is pushed
(git log origin/<branch>). Then give me the merge commands for A → B → C → D into main ONE branch at a time;
after I run each and say "merged", check it (tests, conflicts) before giving the next. Then run all backend tests +
ruff + frontend build, swap stubs for real modules in ports.py, run the integration smoke test (§4), deploy, record
the health log, update progress.md tables, then REWRITE docs/claude-progressive.md for Phase <N+1>
(goals, temporary rules, known issues, contract version) and give me a 📌 COMMIT CHECKPOINT for those changes.
Finally give me the commands to merge main back into every feature branch. Never run git write commands yourself.
Report anything that failed and which session must fix it.
```

### MAIN-API (during Phase 2–3, between gates)
```
Build backend/app/api/ exactly per docs/contracts.md §4 using app.ports (never import session modules directly).
Include X-Admin-Passcode guard on writes, CORS for the Vercel domain, SSE /api/decisions/stream,
and backend/app/scheduler/ jobs: cart-abandonment checker (every 5 min), quiet-hours queue flush at 09:00 IST,
points-expiry scan daily, daily digest 21:00 IST. Add API tests. 📌 COMMIT CHECKPOINT after each working piece.
```

### MAIN-README (Phase 4)
```
Write README.md for judges:
- 1-paragraph pitch ("Don't pay people who'd buy anyway")
- architecture diagram
- "Demo in 5 minutes" script (bot link, /start, /simulate cart, /why, /lab run 3, dashboard Playground, rule edit with impact preview)
- how each judging criterion is met
- setup (local + deploy) and env var names only
- screenshots from docs/screenshots and frontend/screenshots
- data dictionary link
- the CLAUDE.md/docs workflow we used
```

### SUBMIT (Tue 27 Oct, by 10:00)
```
Final submission check: confirm the bot is live (getWebhookInfo, /health, a real /start test), dashboard loads,
no secrets in git history (run gitleaks on full history), README complete, CLAUDE.md present, then give me the
commands to tag v1.0 and push (I run them). Give me the repo URL and bot username to submit, and a checklist of what to keep running until judging.
```

---

## SESSION A: Data & Scoring (`docs/context/context-1.md`)

### A1 (v0.2): Personas, generator, seed
```
You are SESSION A (Data & Scoring) on branch feat/data-scoring. Read CLAUDE.md, docs/claude-progressive.md,
docs/context/context-1.md, docs/contracts.md and docs/detective.md first.
Do Phase 1 of context-1.md: personas.py, catalog.py, festivals.py (verify 2026 dates against a reliable source and
cite it in a comment), generator.py (day-by-day simulation with funnels, seasonality, festival + payday lifts,
churn hazard, messy data), past campaigns incl. Diwali 2025 with a 10% control, and seed.py CLI.
Write tests/data/test_generator_stats.py with the target ranges. Edit only your owned paths.
📌 COMMIT CHECKPOINT after each finished task (never commit yourself). End with the END OF SESSION routine.
```

### A2 (v0.3): Profiles, RFM, churn, policies
```
SESSION A, Phase 2 of docs/context/context-1.md. Read CLAUDE.md and docs/claude-progressive.md first.
Build scoring/rfm.py, churn.py (logistic regression, report AUC), profile.py (build_profile < 50 ms,
assign_policy from a thresholds config), data/onboarding.py (create_profile_from_answers).
Real-time events must update profiles instantly. Tests per policy assignment. Owned paths only. END OF SESSION routine.
```

### A3 (v0.4): Uplift, impact, realism, experiments
```
SESSION A, Phase 3 of docs/context/context-1.md. Build scoring/uplift.py (T-learner, Qini points, sanity checks on
hidden response types), impact.py, realism.py (with benchmark ranges + sources), experiments.py
(treatment vs holdout, margin saved on sure-things, uplift by policy, ROI by offer type, festival vs baseline).
Cache results. Tests. Owned paths only. END OF SESSION routine.
```

### A4 (v1.0): Tuning + data dictionary
```
SESSION A, Phase 4 of docs/context/context-1.md. Tune generator so every benchmark is comfortably in range,
hit performance targets, handle edge cases (0 orders, missing age, brand-new Telegram user), and write
docs/data-dictionary.md for judges. Feature freeze is Mon 18:00, so polish only after that. END OF SESSION routine.
```

---

## SESSION B: Decision Core (`docs/context/context-2.md`)

### B1 (v0.2): Rules engine
```
You are SESSION B (Decision Core) on branch feat/decision-core. Read CLAUDE.md, docs/claude-progressive.md,
docs/context/context-2.md, docs/contracts.md and docs/detective.md first.
Do Phase 1: rules/rule_types.py (applies/constrain/check/describe per RuleType), seed_rules.py (Global, Festival,
all 9 persona policies, Individual examples), engine.py (effective_policy with tighten-only merge, allowed_offers,
evaluate — the ONE function used everywhere), budget pacing. Tests per rule type + hypothesis property test
(10k random decisions, approved ones always inside hard limits). Use app.ports stubs for profiles.
Paste 5 describe() sentences into progress.md. Owned paths only. END OF SESSION routine.
```

### B2 (v0.3): Harness + fallback with mock LLM
```
SESSION B, Phase 2 of docs/context/context-2.md. Build agent/context.py, harness.py (exact pipeline: pre-gate
incl. kill switch/consent/quiet hours/freq/budget/holdout → policy → candidates → LLM loop → evaluate → retry once
→ fallback → coupon → persist Decision + explanation; dry_run support), fallback.py, llm.py (LLMClient protocol +
MockLLM scripted behaviours), explainer.py (deterministic). Write all harness tests listed in "Done when".
Owned paths only. END OF SESSION routine.
```

### B3 (v0.4): Real Groq agent + message validator
```
SESSION B, Phase 3 of docs/context/context-2.md. Build agent/groq_client.py (tool calling, JSON, 20 s timeout,
token bucket, 429 → fallback), tools.py (read-only whitelist, never expose response_type), prompts.py (system prompt
from PLAN §3; customer text wrapped as data), the SINGLE-CALL agent design (harness pre-computes profile/policy/
candidates/impact into the first prompt; max one check_offer; ≤3 tool steps), agent/budget.py LLM budget guard
(daily token budgets per model in runtime settings; 70B → 8B at 80% → rules fallback at 100%; budget.status()),
the batch rule (agent for top 5 only), and message + festival_restriction rule types (numbers in text match params,
expiry, banned phrases, greeting only if opted in and exact, restricted promos).
Run 20 real Groq decisions across policies; log compliance, latency and tokens per decision (target ≤ 3k).
Include a prompt-injection test. Owned paths only. 📌 checkpoints. END OF SESSION routine.
```

### B4 (v1.0): Digest, impact preview, batch mode
```
SESSION B, Phase 4 of docs/context/context-2.md. Build agent/digest.py (code computes stats, fast model writes
5 lines, template fallback), rules/preview.py (impact of a rule change on 500 sampled profiles), batch dry-run mode
(fallback scorer for all, agent for top-N only), and hit the latency targets. END OF SESSION routine.
```

---

## SESSION C: Telegram + Customer Lab (`docs/context/context-3.md`)

### C1 (v0.2): Onboarding, profile, offer card
```
You are SESSION C (Telegram + Lab) on branch feat/telegram-lab. Read CLAUDE.md, docs/claude-progressive.md,
docs/context/context-3.md, docs/contracts.md and docs/detective.md first.
Do Phase 1: bot/app.py (factory + error handler), onboarding.py (/start: consent → categories → frequency →
deal vs quality → optional festival-greeting opt-in → create profile → welcome decision), render.py (Decision →
Telegram HTML card with buttons; NO_OFFER/BLOCKED variants), /profile /help /offers /pause /stop.
Use app.ports.decide (stub fixtures) for now. Test render with snapshot tests. Run locally with --polling.
Owned paths only. END OF SESSION routine.
```

### C2 (v0.3): /simulate, buttons, /why
```
SESSION C, Phase 2 of docs/context/context-3.md. Build bot/simulate.py (all /simulate commands + button menu,
each writes realistic events → decide → deliver, with a one-line status first), button callbacks (Claim, Remind me
tonight at 19:00 IST, Not for me → 14-day category suppression, Why this?), /why, /history, per-user rate limit.
Verify the "Done when" scenarios. Owned paths only. END OF SESSION routine.
```

### C3 (v0.4): Customer Lab
```
SESSION C, Phase 3 of docs/context/context-3.md. Build lab/registry.py (CUSTOMER_BOT_TOKENS → 10 lab customers
with distinct personas), lab/scripts.py (festival-aware persona activity), lab/runner.py (customer bot posts →
event → decide(trigger="lab") → Offer bot replies with @mention → customer bot reacts in character via persona
response model → outcome stored; 2–4 s spacing), /lab run|persona|date|reset, reply-/why, shadow channel delivery.
Remember: bots cannot DM bots; backend orchestrates all. Test with /lab run 5 in the real group. END OF SESSION routine.
```

### C4 (v1.0): Admin + polish + resilience
```
SESSION C, Phase 4 of docs/context/context-3.md. Admin commands (/summary, /killswitch, /campaign run, /impersonate)
gated by ADMIN_TELEGRAM_IDS; polish all copy; handle 403/429/5xx with backoff, idempotent updates; optional Pillow
offer-card image in the Signal palette (graphite header, orange value, amber expiry chip). Save screenshots to docs/screenshots/. END OF SESSION routine.
```

---

## SESSION D: Dashboard (`docs/context/context-4.md`)

### D1 (v0.2): Signal theme, shell, ⌘K
```
You are SESSION D (Dashboard) on branch feat/dashboard. Read CLAUDE.md (esp. §7 Design — the "Signal" system),
docs/claude-progressive.md, docs/context/context-4.md, docs/contracts.md and docs/detective.md first.
Do Phase 1: scaffold Vite+React+TS+Tailwind v4+shadcn+TanStack Query+cmdk+Recharts in frontend/, theme.css with the
Signal tokens (light+dark: cool monochrome, dark sidebar, ONE orange signal accent, violet second series, amber warnings),
Geist + Geist Mono (tabular) fonts, restyled shadcn (8px cards, 6px controls, hairlines, no gradients), app shell with
dark left sidebar + top bar (kill switch, budget meter, "Upcoming moments" chip, bot link/QR, ⌘K, admin passcode),
typed api.ts with VITE_USE_MOCKS, mock JSON from contracts §5, shared components (Kpi with hero variant, PipelineLens,
DataTable, ExplanationCard, RuleCheckList, badges, Money, EmptyState, WhyThisPage). No beige/skin tones, no regional
decoration, no banned patterns (T06, T08). Owned paths only. 📌 COMMIT CHECKPOINT after each finished task.
END OF SESSION routine.
```

### D2 (v0.3): Overview + Decisions
```
SESSION D, Phase 2 of docs/context/context-4.md. Build Overview (KPI strip with ▲▼, live feed via SSE with polling
fallback, funnel, agent vs fallback share, AI digest card, margin-protected callout) and Decisions (filters, table,
drawer with ExplanationCard, Telegram-style message preview, agent trace timeline, RuleCheckList, profile snapshot).
Works on mocks and on the real API URL. END OF SESSION routine.
```

### D3 (v0.4): Rules editor + Customers
```
SESSION D, Phase 3 of docs/context/context-4.md. Build Rules & Policies (layer tabs, sentence cards with inline
values, toggle, hard/soft tag, impact preview before save, version history + revert, "who is in this policy now")
and Customers (segment scatter with colour+shape, table, drawer with scores in plain words, timeline, decisions,
Simulate trigger buttons, Run decision now). Verify the marketer flow in "Done when". END OF SESSION routine.
```

### D4 (v1.0): Experiments, Festivals, Realism, Playground, polish
```
SESSION D, Phase 4 of docs/context/context-4.md. Build Experiments (with auto one-sentence takeaways), Festivals
(calendar + phase strategy editor + greeting preview), Realism (benchmark bands + ✓/✗), Playground (step-by-step
pipeline trace, time-travel date, force-LLM-failure toggle; the demo hero), campaign dry-run, then polish
(skeletons, empty states, responsive, favicon/wordmark) and save screenshots to frontend/screenshots/.
END OF SESSION routine.
```
