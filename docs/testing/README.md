# Scenario test pack

Black-box tests of the live engine: 20 scenarios (`scenarios.csv`) are run as **Playground dry runs**, so nothing is ever sent to anyone or stored, and every result is checked automatically. They complement the 362 unit tests in `backend/tests`.

## Run it

From the repository root:

```bash
python docs/testing/run_scenarios.py
```

That runs every scenario with the AI switched off for each run (`force_llm_fail`), so it uses **no AI tokens** and shows the rules fallback. Add `--with-ai` to also send the rows marked `use_ai=yes` through the real AI agent (about 6 agent calls):

```bash
python docs/testing/run_scenarios.py --with-ai
```

Against a local server: `--api http://localhost:8000`. The script uses only the Python standard library. It prints one line per decision, writes `results.csv` next to it and exits with code 1 if anything fails.

## What the data covers

| Scenarios | Customers | Checks |
|---|---|---|
| S01–S02 | 2 live cart abandoners | an offer, only allowed types, % off ≤ 5 |
| S03–S04 | 2 live VIPs | **never** a % or ₹ discount |
| S05–S06 | 2 live deal hunters | % off ≤ 10 and only with a minimum basket ≥ ₹999 |
| S07 | high returners | points only |
| S08 | window shoppers | allowed types, ₹ off ≤ 150 |
| S09–S11 | new users, at-risk, dormant | their % caps (15, 20, 15) |
| S12 | Lab customer Meera (sleeping dog) | **no offer** |
| S13–S14 | a fixed customer, with and without the AI | the fallback decides when the AI is off; any "no offer" has a reason |
| S15–S16 | festival triggers during Diwali build-up and last-minute (time-travelled) | only the current festival's exact greeting may appear; deal-hunter cap still holds |
| S17–S18 | payday, points expiry | valid decision |
| S19 | default policy | valid decision |
| S20 | 25 random synthetic customers × random triggers | global invariants |

**Global invariants checked on every decision:** a known status and decider; an explanation with a rules line; message ≤ 280 characters; cost ≥ 0; % ≤ 30, ₹ ≤ 500, multiplier ≤ 3; no chosen offer with a failed validation; and when the AI is forced off, the AI never decided.

Customers are picked live (`policy:<name>`, `random:<n>`) because policies change as real time passes: a cart older than 3 days no longer makes someone a cart abandoner. Lab customers are excluded from the policy and random picks because their weekly caps fill up during Lab rounds.

## Not covered here (covered by the unit tests)
Quiet-hours queueing (Playground runs report `DRY_RUN`), the kill switch and `/stop` and `/pause` (they need writes), festival opt-in (not exposed by the API), the 48 h post-purchase rule (needs a stored purchase; try it in Telegram with `/impersonate`, then `/simulate purchase` and `/simulate cart`).

## Last run (26 Oct 2026, production)
56/56 decisions passed without the AI; 56/56 with `--with-ai` (4 decisions made by the agent, all within their policy limits).
