// In-memory mock backend for contracts.md §4. State resets on page reload.
import type {
  Budget, CampaignDryRun, CustomerDetail, CustomerProfile, Decision, DecisionLight, Digest,
  Festival, Health, KillSwitch, Kpis, Meta, Page, Rule, RuleImpact, SchedulerStatus, TriggerType,
} from '@/lib/types'
import { CUSTOMERS, DECISIONS, eventsFor, FESTIVALS, fullDecision, KPIS, makeDecision, RULES } from './seed'

const state = {
  killswitch: { on: false, changed_at: null } as KillSwitch,
  rules: RULES.map((r) => ({ ...r })),
  history: new Map<string, Rule[]>(),
}

export class MockHttpError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

type Handler = (m: RegExpMatchArray, q: URLSearchParams, body: unknown) => unknown
const routes: [string, RegExp, Handler][] = []
const on = (method: string, pattern: string, h: Handler) =>
  routes.push([method, new RegExp(`^${pattern.replace(/:\w+/g, '([^/]+)')}$`), h])

const byTsDesc = (a: DecisionLight, b: DecisionLight) => b.ts.localeCompare(a.ts)

on('GET', '/health', (): Health => ({
  ok: true, version: '0.4-mock',
  llm_budget: {
    agent: { used: 13100, limit: 80000, model: 'openai/gpt-oss-120b' },
    fast: { used: 0, limit: 400000, model: 'openai/gpt-oss-20b' },
    mode: '70b',
  },
}))
on('GET', '/api/meta', (): Meta => ({
  bot_username: 'navpreet_offers_bot', lab_group_link: null, now: new Date().toISOString(), demo_time_override: null,
}))
on('GET', '/api/kpis', (): Kpis => KPIS)
on('GET', '/api/budget', (): Budget => ({
  today_used: 13200, today_cap: 25000,
  festival: { name: 'karwa_chauth_2026', phase: 'build_up', days_to: 5, budget_left: 31200 },
}))
on('GET', '/api/settings/killswitch', () => state.killswitch)
on('POST', '/api/settings/killswitch', (_m, _q, body) => {
  state.killswitch = { on: Boolean((body as { on: boolean }).on), changed_at: new Date().toISOString() }
  return state.killswitch
})

// Simulates new traffic so the live stream moves: roughly one new decision every 7 s.
let lastTick = Date.now()
function tick() {
  const due = Math.min(3, Math.floor((Date.now() - lastTick) / 7000))
  for (let i = 0; i < due; i++) DECISIONS.push(makeDecision(new Date()))
  if (due) lastTick = Date.now()
}

on('GET', '/api/decisions', (_m, q): Page<DecisionLight> => {
  tick()
  const text = q.get('q')?.toLowerCase()
  const items = DECISIONS.filter((d) =>
    (!q.get('status') || d.status === q.get('status')) &&
    (!q.get('decided_by') || d.decided_by === q.get('decided_by')) &&
    (!q.get('policy') || d.policy === q.get('policy')) &&
    (!q.get('trigger') || d.trigger === q.get('trigger')) &&
    (!q.get('festival') || d.festival === q.get('festival') || Boolean(d.festival?.startsWith(`${q.get('festival')}_`))) &&
    (!text || `${d.id} ${d.customer_id} ${d.first_name} ${d.explanation_title}`.toLowerCase().includes(text)) &&
    (!q.get('cursor') || d.ts < q.get('cursor')!),
  ).sort(byTsDesc)
  // Same paging as the API: `next` is the ts of the last item when more remain.
  const limit = Math.min(200, Number(q.get('limit') ?? 50))
  const page = items.slice(0, limit)
  return { items: page, next: items.length > limit ? page[page.length - 1].ts : null }
})
on('GET', '/api/decisions/:id', (m): Decision => {
  const d = DECISIONS.find((x) => x.id === decodeURIComponent(m[1]))
  if (!d) throw new MockHttpError(404, `Decision ${m[1]} not found`)
  return fullDecision(d)
})

on('GET', '/api/customers', (_m, q): Page<CustomerProfile> => {
  const text = q.get('q')?.toLowerCase()
  const items = CUSTOMERS.filter((c) =>
    (!q.get('policy') || c.policy === q.get('policy')) &&
    (!text || `${c.customer_id} ${c.first_name}`.toLowerCase().includes(text)),
  )
  return { items: items.slice(0, Number(q.get('limit') ?? 100)), next: null }
})
on('GET', '/api/customers/:id', (m): CustomerDetail => {
  const profile = CUSTOMERS.find((c) => c.customer_id === m[1])
  if (!profile) throw new MockHttpError(404, `Customer ${m[1]} not found`)
  return { profile, events: eventsFor(profile), decisions: DECISIONS.filter((d) => d.customer_id === m[1]).sort(byTsDesc) }
})
const simulate = (customer_id: string, trigger: TriggerType): Decision => {
  const c = CUSTOMERS.find((x) => x.customer_id === customer_id) ?? CUSTOMERS[0]
  const blocked = state.killswitch.on || trigger === 'manual'
  return fullDecision({
    ...DECISIONS[0], id: `DSIM-${Date.now() % 100000}`, ts: new Date().toISOString(), customer_id: c.customer_id,
    first_name: c.first_name, policy: c.policy, trigger,
    status: blocked ? 'BLOCKED' : 'DRY_RUN', decided_by: blocked ? 'BLOCKED_PREGATE' : 'AGENT',
    explanation_title: blocked ? `Blocked: ${state.killswitch.on ? 'Kill switch on' : 'manual trigger'}` : DECISIONS[0].explanation_title,
  })
}
on('POST', '/api/customers/:id/simulate', (m, _q, body) => simulate(m[1], (body as { trigger: TriggerType }).trigger))
on('POST', '/api/playground/run', (_m, _q, body) => {
  const b = body as { customer_id: string; trigger: TriggerType }
  return simulate(b.customer_id, b.trigger)
})

on('GET', '/api/rules', (_m, q): Rule[] => state.rules.filter((r) => !q.get('layer') || r.layer === q.get('layer')))
on('PATCH', '/api/rules/:id', (m, _q, body): Rule => {
  const i = state.rules.findIndex((r) => r.id === m[1])
  if (i < 0) throw new MockHttpError(404, `Rule ${m[1]} not found`)
  const old = state.rules[i]
  state.history.set(old.id, [...(state.history.get(old.id) ?? []), old])
  const patch = body as Partial<Pick<Rule, 'params' | 'enabled' | 'priority'>>
  // Stand-in for the server's describe(): swap changed numbers inside the sentence.
  let description = old.description
  for (const [k, v] of Object.entries(patch.params ?? {})) {
    const was = old.params[k]
    if (typeof was === 'number' && typeof v === 'number')
      description = description.replace(new RegExp(`(?<![\\d])${was.toLocaleString('en-US')}(?![\\d])`), v.toLocaleString('en-US'))
  }
  state.rules[i] = {
    ...old, ...patch, description, params: { ...old.params, ...patch.params }, version: old.version + 1,
    updated_by: 'dashboard', updated_at: new Date().toISOString(),
  }
  return state.rules[i]
})
on('POST', '/api/rules/preview', (): RuleImpact => ({
  customers_affected: 312, budget_delta: -18400,
  examples: CUSTOMERS.slice(0, 3).map((c) => ({ customer_id: c.customer_id, first_name: c.first_name, policy: c.policy })),
}))
// Same order as the API: current version first, then older snapshots, newest first.
on('GET', '/api/rules/:id/versions', (m): Rule[] => [
  ...state.rules.filter((r) => r.id === m[1]), ...[...(state.history.get(m[1]) ?? [])].reverse(),
])
on('POST', '/api/rules/:id/revert/:version', (m): Rule => {
  const old = state.history.get(m[1])?.find((r) => r.version === Number(m[2]))
  const i = state.rules.findIndex((r) => r.id === m[1])
  if (!old || i < 0) throw new MockHttpError(404, 'Version not found')
  state.rules[i] = { ...old, version: state.rules[i].version + 1, updated_at: new Date().toISOString() }
  return state.rules[i]
})

on('GET', '/api/festivals', (): Festival[] => FESTIVALS)
on('PATCH', '/api/festivals/:id', (m, _q, body): Festival => {
  const i = FESTIVALS.findIndex((f) => f.id === m[1])
  if (i < 0) throw new MockHttpError(404, `Festival ${m[1]} not found`)
  FESTIVALS[i] = { ...FESTIVALS[i], ...(body as Partial<Festival>) }
  return FESTIVALS[i]
})
on('GET', '/api/scheduler', (): SchedulerStatus => {
  const at = (h: number) => new Date(Date.now() + h * 3_600_000).toISOString()
  return { running: true, next_runs: { cart_abandonment: at(0.1), daily_digest: at(5), flush_quiet_queue: at(17), points_expiry: at(18) } }
})
on('POST', '/api/scheduler/run/:job', (m) => ({ job: m[1], ran: true, decisions: 0 }))
on('GET', '/api/digest', (): Digest => ({
  day: new Date().toISOString().slice(0, 10),
  text: 'Cart abandoners drove most claims today; free shipping beat 5% off on cost. 4 VIPs were left alone because they buy anyway, saving ₹3,120 of margin.',
  generated_by: 'mock',
}))
on('POST', '/api/campaigns/dry-run', (): CampaignDryRun => {
  const rows = DECISIONS.slice(0, 30)
  const sent = rows.filter((d) => d.final_offer_id)
  return {
    rows,
    totals: {
      customers: rows.length, would_send: sent.length, no_offer: rows.filter((d) => d.status === 'NO_OFFER').length,
      blocked: rows.filter((d) => d.status === 'BLOCKED').length, over_budget: 0,
      cost: sent.reduce((s, d) => s + d.cost, 0), expected_incremental_profit: sent.reduce((s, d) => s + d.expected_incremental_profit, 0),
    },
  }
})

export async function mockFetch(method: string, path: string, body?: unknown): Promise<unknown> {
  const url = new URL(path, 'http://mock')
  await new Promise((res) => setTimeout(res, 120 + Math.random() * 180))
  for (const [m, re, h] of routes) {
    const match = m === method ? url.pathname.match(re) : null
    if (match) return structuredClone(h(match, url.searchParams, body))
  }
  throw new MockHttpError(404, `No mock for ${method} ${url.pathname}`)
}
