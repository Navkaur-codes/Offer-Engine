# context-4.md: Session D, Analytics Dashboard (React)

**Branch:** `feat/dashboard`
**Worktree:** its own worktree
**Read first:** `CLAUDE.md` (especially §7, Design), `docs/claude-progressive.md`, `docs/contracts.md §2, §4, §5`, `docs/detective.md`, `docs/PLAN.md §7`

> **Final status (27 Oct 2026): done, merged into `main`, live** at https://offer-engine-nu.vercel.app. Signal design system, app shell with kill switch, budget meter, degraded-AI chip, bot link + QR and ⌘K; Overview (hero KPI, live stream, funnel, who decided, margin card with a live "today" line, Automations with Run now and the **personal picks run report**), Decisions with the Pipeline Lens, Rules as sentences with impact preview and versions, Customers, Experiments, Festivals, Realism, Playground with "force LLM failure", campaign dry-run; Lighthouse accessibility 100. Proposed but not built: receipt panel for ₹91,760, numbered sidebar flow. This brief is kept as the historical plan for Session D.

## Mission
A dashboard a **marketing team understands and adjusts without help**:
- distinctive, modern **"Signal"** design: cool monochrome with one orange signal accent; not beige or skin-toned, not the blue-green AI look;
- 80% of actions are one click or ⌘K away;
- results that are easy to read.
This session covers the **usability** and **design** criteria, and makes everything the other sessions build *visible* to judges.

## Owned paths
`frontend/**` (all of it)

## Never touch
Anything in `backend/`, or `docs/` except the progress.md and sessions.md entries.

## Consumes
The REST API in `contracts.md §4`. Until it is live, use **mock JSON** in `frontend/src/mocks/`, built from `contracts.md §5`, and switch with `VITE_USE_MOCKS=1`.

## Produces
The deployable Vite app for Vercel. `VITE_API_URL` points at the Render backend.

---

## Phase 1 (v0.2): Signal theme, app shell, ⌘K, kill switch
**Tasks:**
1. Scaffold with Vite + React + TypeScript, Tailwind v4, shadcn/ui, TanStack Query, react-router, cmdk and Recharts.
2. `src/theme.css` defines the **Signal** tokens from `CLAUDE.md §7`, with light and dark modes.
   - **Fonts:** Geist for everything (SemiBold, tight tracking for titles and KPIs); Geist Mono with tabular numbers for all figures, ₹ and codes.
   - **Restyle shadcn:** 8px cards, 6px controls, hairline borders, no shadows except menus, **no gradients**.
   - `--signal` (orange) is used sparingly: primary button, hero KPI, "sent by AI" marks. Everything else stays monochrome.
3. App shell:
   - **Dark left sidebar** (`--rail`) with nav: Overview, Decisions, Rules, Customers, Experiments, Festivals, Realism, Playground. The active item is marked with a signal-orange bar.
   - **Top bar:**
     - **Kill switch** with a live status dot and a confirm dialog;
     - **budget meter** (today's use and festival pool);
     - **"Upcoming moments" chip**: neutral, with an amber countdown (e.g. "Dhanteras in 13 days · build-up"), and no regional decoration;
     - **bot link/QR** popover;
     - **⌘K**;
     - an admin passcode field that unlocks edits and is stored in sessionStorage.
4. ⌘K palette: find customer, open decision by ID, edit rule…, run Playground for…, campaign dry-run, toggle kill switch, open bot, switch theme.
5. `src/lib/api.ts`: a typed client whose types mirror `contracts.md`, a mocks switch, and error toasts.
6. Shared components:
   - `Kpi` (big Geist SemiBold number, ▲▼ delta, sparkline; a `hero` variant in signal orange, used once per page at most);
   - `PipelineLens` (step chips *Pre-gate → Policy → Agent → Validator → Sent*, each ✓/✗/↺ with a tooltip). The signature element; reused in Decisions and Playground;
   - `DataTable` (TanStack, dense, sticky header);
   - `ExplanationCard`;
   - `RuleCheckList` (✓/✗ with text);
   - `PolicyBadge`, `DecidedByBadge`, `Money`, `EmptyState` (always shows a hint and an action);
   - `WhyThisPage`, a one-line marketer note on every page.

**Done when:**
- The shell runs on mocks in both light and dark modes.
- Lighthouse accessibility score is at least 90.
- The design shows no banned patterns (T06, T08): no beige or skin tones, no gradients, no regional decoration.

## Phase 2 (v0.3): Overview + Decisions log
**Tasks:**
1. **Overview:**
   - KPI strip: sent today, claim rate, incremental revenue vs. holdout, budget used, blocked by rules, margin saved.
   - **Live decision feed** (SSE, with polling as fallback). Each row has a time, name, policy badge, headline and decided-by badge, and opens a drawer.
   - Funnel (sent → claimed → redeemed).
   - Agent vs. fallback share.
   - **Today's AI digest** card.
   - **"Margin protected by not discounting sure-things"** callout.
2. **Decisions:**
   - Filterable table with filters for status, decided_by, policy, trigger, festival and search.
   - The row drawer shows:
     - the `ExplanationCard`;
     - the Telegram message preview, styled like Telegram;
     - the **agent trace timeline** (tool calls, ms);
     - the `RuleCheckList`;
     - the profile snapshot.
   - Copy-link for the decision.

**Done when:** both pages work on mocks *and* on the real API (once main deploys it), and a decision can be found and understood in fewer than 3 clicks.

## Phase 3 (v0.4): Rules editor + Customers
**Before starting:**
- Switch to the **real API**. It's live at `https://offer-engine-n4jx.onrender.com` with real decisions, and locally at `uvicorn app.main:app --app-dir backend`.
- Adopt contracts **v1.1**: `Kpis.deltas` keys are the KPI field names with fractional changes (null = no arrow); `DecisionLight.festival`; the `festival=` filter.
- Keep mocks only as a fallback (`VITE_USE_MOCKS=1`).
- Deploy to **Vercel** happens in this phase. Main gives the user the steps; make sure `VITE_API_URL` is read at build time.
**Tasks:**
1. **Rules & Policies** (the most important page for usability):
   - Tabs for the layers: Global · Festival · Persona · Individual.
   - Each rule is a **sentence card** with inline editable values, e.g. "Deal hunters can get at most [10]% off, only on baskets above ₹[999]", plus an enabled toggle and a hard/soft tag.
   - Editing calls `POST /api/rules/preview` and shows an **impact preview** ("Affects 312 customers · budget −₹18,400 · 3 examples") before Save.
   - Version history drawer with **Revert**.
   - Persona policy cards show "who is in this policy now (n)", with a link to Customers.
2. **Customers:**
   - Segment scatter (recency × value, coloured by policy; colour plus shape for accessibility) and a searchable table.
   - The customer drawer shows:
     - profile scores in plain words;
     - an event timeline;
     - past decisions;
     - **Simulate trigger** buttons (cart, inactive, festival…) that call `POST /api/customers/{id}/simulate`;
     - **Run decision now** (dry run).

**Done when:** a marketer can change a cap, see its impact, save it, see a blocked decision caused by it, and revert it, without reading any docs.

## Phase 4 (v1.0): Experiments, Festivals, Realism, Playground, polish
**Tasks:**
1. **Experiments:**
   - treatment vs. holdout bars;
   - incremental revenue and profit KPIs;
   - uplift by policy;
   - ROI by offer type;
   - Qini curve;
   - festival vs. baseline lift.
   - Every chart gets a one-sentence takeaway written in code from the data, e.g. "At-risk customers respond 3× better to win-back than average".
2. **Festivals:**
   - Calendar strip with phases, editable dates, hero categories, budget and per-phase strategy (PATCH).
   - A greeting preview with an "opt-in only" badge.
3. **Realism:** Pareto curve, funnel, retention cohort heatmap, seasonality line, AOV and return rate by category. Each chart shows its benchmark band ("target 65–80%") and ✓/✗.
4. **Playground:**
   - Choose a customer, trigger, optional date (time-travel) and optional "force LLM failure" toggle.
   - Run, then show the trace **step by step** (pre-gate → policy → candidates → agent tool calls → validator → fallback?) with the final card preview.
   - This is the demo hero.
5. **Campaign dry-run** (in the ⌘K palette and on the Customers page): pick a policy or festival and a budget, then run, then see a table of who gets what, the cost and the blocked reasons, with totals.
6. Polish:
   - loading skeletons;
   - empty states;
   - responsive down to 1280 px, plus a usable mobile view of Overview;
   - favicon and a simple wordmark;
   - screenshots saved to `frontend/screenshots/` for the README.

## Stub strategy
Mocks are mandatory until the API is live. Keep mock data realistic: 50 decisions across all policies and statuses, 30 customers, and the full seed rule set. Copy them from the contracts examples and expand them.

## Commands
```
cd frontend && npm i && npm run dev        # VITE_USE_MOCKS=1
npm run lint && npm run build
```

## Detective traps
T06, T07, T08, T09, T16, T24, T27.

## Handoff checklist
- [ ] `npm run build` passes, lint clean, every finished task given to the user as a 📌 COMMIT CHECKPOINT, and the user confirmed it is pushed to `feat/dashboard`.
- [ ] Each page has a `WhyThisPage` note and one primary action.
- [ ] `progress.md` entry and `sessions.md` row updated. API mismatches are listed as contract change requests.
