"""Runs docs/testing/scenarios.csv against the Holdout API as Playground dry runs and checks the results.

Dry runs are never sent or stored, so this is safe against production. Standard library only.

    python docs/testing/run_scenarios.py                      # production, rules fallback only (no AI tokens)
    python docs/testing/run_scenarios.py --with-ai            # also runs the use_ai=yes rows through the AI agent
    python docs/testing/run_scenarios.py --api http://localhost:8000

Writes docs/testing/results.csv and exits with code 1 if any check fails.

`customer` is a fixed id (C000129), `policy:<name>` (the first live customers in that policy) or `random:<n>`.
`expect` is a ';' list of checks; every decision is also checked against the global invariants (see `universal`).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
STATUSES = {"SENT", "QUEUED", "NO_OFFER", "BLOCKED", "HELD_OUT", "DRY_RUN"}
DECIDERS = {"AGENT", "AGENT_RETRY", "RULES_FALLBACK", "BLOCKED_PREGATE", "HOLDOUT"}
DISCOUNTS = {"pct_off", "flat_off"}
LAB = {f"C9000{i:02d}" for i in range(1, 11)}


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path, timeout=120) as r:
            return json.load(r)

    def post(self, path: str, body: dict):
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)


def customers_for(api: Api, spec: str, rng: random.Random) -> list[str]:
    if spec.startswith("policy:"):
        items = api.get(f"/api/customers?policy={spec.split(':', 1)[1]}&limit=20")["items"]
        ids = [c["customer_id"] for c in items if c["customer_id"].startswith("C") and c["customer_id"] not in LAB]
        return ids[:2]
    if spec.startswith("random:"):
        n = int(spec.split(":", 1)[1])
        items = api.get("/api/customers?limit=100")["items"]
        ids = [c["customer_id"] for c in items if c["customer_id"].startswith("C") and c["customer_id"] not in LAB]
        return rng.sample(ids, min(n, len(ids)))
    return [spec]


def offer_type(d: dict) -> str | None:
    if not d.get("final_offer_id"):
        return None
    for c in d.get("candidates", []):
        if c.get("offer_id") == d["final_offer_id"]:
            return c.get("type")
    return None


def universal(d: dict, forced: bool) -> list[str]:
    """Invariants every decision must satisfy (CLAUDE.md non-negotiables)."""
    bad = []
    if d.get("status") not in STATUSES:
        bad.append(f"unknown status {d.get('status')}")
    if d.get("decided_by") not in DECIDERS:
        bad.append(f"unknown decided_by {d.get('decided_by')}")
    exp = d.get("explanation") or {}
    if not exp.get("title") or not exp.get("rules_line"):
        bad.append("missing explanation")
    if forced and d.get("decided_by") in ("AGENT", "AGENT_RETRY"):
        bad.append("force_llm_fail ignored: the agent decided")
    if d.get("final_offer_id"):
        p = d.get("final_params") or {}
        if len(d.get("message") or "") > 280:
            bad.append(f"message {len(d['message'])} chars > 280")
        if d.get("cost", 0) < 0:
            bad.append("negative cost")
        if p.get("pct", 0) > 30 or p.get("amount", 0) > 500 or p.get("multiplier", 0) > 3:
            bad.append(f"global cap exceeded {p}")
        v = d.get("validation") or {}
        if v and v.get("ok") is False:
            bad.append("an offer was chosen although validation failed")
    return bad


def check(d: dict, expect: str, greetings: list[str]) -> list[str]:
    bad, typ, p = [], offer_type(d), d.get("final_params") or {}
    has_offer = bool(d.get("final_offer_id"))
    for rule in filter(None, (x.strip() for x in expect.split(";"))):
        if rule == "offer" and not has_offer and d.get("status") not in ("BLOCKED", "HELD_OUT"):
            bad.append(f"expected an offer, got {d.get('status')}: {d.get('fallback_reason')}")
        elif rule == "no_offer" and has_offer:
            bad.append(f"expected no offer, got {d['final_offer_id']}")
        elif rule == "no_discount" and typ in DISCOUNTS:
            bad.append(f"discount {typ} sent to a policy that forbids it")
        elif rule.startswith("types=") and typ and typ not in rule[6:].split("|"):
            bad.append(f"offer type {typ} not in {rule[6:]}")
        elif rule.startswith("pct<=") and p.get("pct", 0) > float(rule[5:]):
            bad.append(f"pct {p.get('pct')} > {rule[5:]}")
        elif rule.startswith("amount<=") and p.get("amount", 0) > float(rule[8:]):
            bad.append(f"amount {p.get('amount')} > {rule[8:]}")
        elif rule.startswith("min_basket>=") and typ == "pct_off" and p.get("min_basket", 0) < float(rule[12:]):
            bad.append(f"min_basket {p.get('min_basket')} < {rule[12:]}")
        elif rule == "fallback_only" and d.get("decided_by") in ("AGENT", "AGENT_RETRY"):
            bad.append("agent decided although the LLM was forced off")
        elif rule == "offer_or_reasoned_no_offer" and not has_offer and not d.get("fallback_reason"):
            bad.append("no offer and no reason")
        elif rule == "festival_safe":
            # like the validator: only the current festival's exact greeting from the festivals table may appear
            allowed, msg = (d.get("context") or {}).get("greeting"), (d.get("message") or "").lower()
            for g in greetings:
                if g.lower() in msg and g != allowed:
                    bad.append(f"greeting '{g}' used outside its festival")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://offer-engine-n4jx.onrender.com")
    ap.add_argument("--with-ai", action="store_true", help="run use_ai=yes rows through the AI agent (uses tokens)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    api, rng = Api(args.api), random.Random(args.seed)
    greetings = sorted({f["greeting"] for f in api.get("/api/festivals") if f.get("greeting")})

    results, failures = [], 0
    with open(HERE / "scenarios.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        triggers = row["trigger"].split("|")
        use_ai = row["use_ai"] == "yes" and args.with_ai
        try:
            ids = customers_for(api, row["customer"], rng)
        except urllib.error.URLError as exc:
            print(f"{row['id']}: cannot list customers ({exc})")
            return 1
        if not ids:
            results.append({**row, "customer_id": "-", "status": "SKIP", "decided_by": "", "offer": "", "problems": "no customer in this policy"})
            continue
        for cid in ids:
            meta = json.loads(row["meta"] or "{}")
            if not use_ai:
                meta["force_llm_fail"] = True
            body = {"customer_id": cid, "trigger": rng.choice(triggers), "meta": meta}
            if row["now"]:
                body["now"] = row["now"]
            try:
                d = api.post("/api/playground/run", body)
            except urllib.error.HTTPError as exc:
                d, problems = {}, [f"HTTP {exc.code}: {exc.read()[:120]!r}"]
            else:
                problems = universal(d, forced=not use_ai) + check(d, row["expect"], greetings)
            failures += bool(problems)
            results.append(
                {
                    **row,
                    "customer_id": cid,
                    "trigger": body["trigger"],
                    "status": d.get("status", "ERROR"),
                    "decided_by": d.get("decided_by", ""),
                    "offer": d.get("final_offer_id") or "",
                    "problems": " | ".join(problems),
                }
            )
            mark = "FAIL" if problems else "ok  "
            print(f"{mark} {row['id']} {cid:<14} {body['trigger']:<16} {d.get('status', 'ERROR'):<9} "
                  f"{d.get('decided_by', ''):<16} {d.get('final_offer_id') or '-':<14} {' | '.join(problems)}")

    out = HERE / "results.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(f"\n{len(results) - failures}/{len(results)} decisions passed · details in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
