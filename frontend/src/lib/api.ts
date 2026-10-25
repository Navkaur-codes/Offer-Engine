// Typed client for contracts.md §4 (v1.1). Talks to the real API; mocks only when VITE_USE_MOCKS=1.
import { toast } from 'sonner'
import type {
  Budget, CampaignDryRun, CustomerDetail, CustomerProfile, Decision, DecisionFilters, DecisionLight,
  Digest, ExperimentStats, Festival, Health, KillSwitch, Kpis, Meta, Offer, Page, PolicyName,
  RealismStats, Rule, RuleImpact, RuleLayer, SchedulerStatus, TriggerType,
} from './types'

const PROD_API = 'https://offer-engine-n4jx.onrender.com'
const API_URL = (import.meta.env.VITE_API_URL || PROD_API).replace(/\/$/, '')
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === '1'

const PASSCODE_KEY = 'oe-admin-passcode'
export const passcode = {
  get: (): string | null => {
    try {
      return sessionStorage.getItem(PASSCODE_KEY)
    } catch {
      return null
    }
  },
  set: (v: string | null) => {
    try {
      if (v) sessionStorage.setItem(PASSCODE_KEY, v)
      else sessionStorage.removeItem(PASSCODE_KEY)
    } catch {
      /* private mode: passcode lives for this tab only */
    }
    window.dispatchEvent(new Event('oe-passcode'))
  },
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

type Method = 'GET' | 'POST' | 'PATCH'

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  try {
    if (USE_MOCKS) {
      const { mockFetch, MockHttpError } = await import('@/mocks/handlers')
      if (method !== 'GET' && !passcode.get()) throw new ApiError(401, 'Enter the admin passcode to make changes.')
      try {
        return (await mockFetch(method, path, body)) as T
      } catch (e) {
        if (e instanceof MockHttpError) throw new ApiError(e.status, e.message)
        throw e
      }
    }
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const code = passcode.get()
    if (method !== 'GET' && code) headers['X-Admin-Passcode'] = code
    const res = await fetch(API_URL + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
    if (!res.ok) {
      const detail = await res.json().catch(() => null)
      throw new ApiError(res.status, (detail as { detail?: string } | null)?.detail ?? `${res.status} ${res.statusText}`)
    }
    return (await res.json()) as T
  } catch (e) {
    const err = e instanceof ApiError ? e : new ApiError(0, 'Backend unreachable. Is the Render service awake?')
    toast.error(err.status === 401 || err.status === 403 ? 'Admin passcode needed' : 'Request failed', {
      description: err.message,
    })
    throw err
  }
}

function qs(params: object): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

const get = <T,>(path: string) => request<T>('GET', path)
const post = <T,>(path: string, body: unknown = {}) => request<T>('POST', path, body)
const patch = <T,>(path: string, body: unknown) => request<T>('PATCH', path, body)

export const api = {
  health: () => get<Health>('/health'),
  meta: () => get<Meta>('/api/meta'),
  kpis: (day?: string) => get<Kpis>(`/api/kpis${qs({ day })}`),
  decisions: (f: DecisionFilters = {}) => get<Page<DecisionLight>>(`/api/decisions${qs(f)}`),
  decision: (id: string) => get<Decision>(`/api/decisions/${encodeURIComponent(id)}`),
  decisionStreamUrl: () => (USE_MOCKS ? null : `${API_URL}/api/decisions/stream`),
  customers: (f: { q?: string; policy?: PolicyName; limit?: number; cursor?: string } = {}) =>
    get<Page<CustomerProfile>>(`/api/customers${qs(f)}`),
  customer: (id: string) => get<CustomerDetail>(`/api/customers/${encodeURIComponent(id)}`),
  simulate: (id: string, trigger: TriggerType, meta: object = {}) =>
    post<Decision>(`/api/customers/${encodeURIComponent(id)}/simulate`, { trigger, meta }),
  playground: (b: { customer_id: string; trigger: TriggerType; meta?: object; now?: string }) =>
    post<Decision>('/api/playground/run', { meta: {}, ...b }),
  rules: (layer?: RuleLayer) => get<Rule[]>(`/api/rules${qs({ layer })}`),
  updateRule: (id: string, b: Partial<Pick<Rule, 'params' | 'enabled' | 'priority'>>) => patch<Rule>(`/api/rules/${id}`, b),
  previewRule: (rule: Rule) => post<RuleImpact>('/api/rules/preview', { rule }),
  ruleVersions: (id: string) => get<Rule[]>(`/api/rules/${id}/versions`),
  revertRule: (id: string, version: number) => post<Rule>(`/api/rules/${id}/revert/${version}`),
  offers: () => get<Offer[]>('/api/offers'),
  festivals: () => get<Festival[]>('/api/festivals'),
  updateFestival: (id: string, b: Partial<Festival>) => patch<Festival>(`/api/festivals/${id}`, b),
  campaignDryRun: (b: { policy?: PolicyName; festival?: string; offer_ids?: string[]; budget: number; limit: number }) =>
    post<CampaignDryRun>('/api/campaigns/dry-run', b),
  experiments: (start?: string, end?: string) => get<ExperimentStats>(`/api/experiments${qs({ start, end })}`),
  realism: () => get<RealismStats>('/api/realism'),
  digest: (day?: string) => get<Digest>(`/api/digest${qs({ day })}`),
  killswitch: () => get<KillSwitch>('/api/settings/killswitch'),
  setKillswitch: (on: boolean) => post<KillSwitch>('/api/settings/killswitch', { on }),
  budget: () => get<Budget>('/api/budget'),
  scheduler: () => get<SchedulerStatus>('/api/scheduler'),
  runJob: (job: string) => post<Record<string, unknown>>(`/api/scheduler/run/${encodeURIComponent(job)}`),
}
