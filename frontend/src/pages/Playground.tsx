import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { Play, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { PipelineLens } from '@/components/PipelineLens'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import { POLICY_LABEL, TRIGGER_LABEL } from '@/lib/labels'
import type { Decision, PolicyName, TriggerType } from '@/lib/types'
import { cn } from '@/lib/utils'
import { StepView } from './playground/StepView'
import { buildSteps } from './playground/Steps'

const TRIGGERS: TriggerType[] = ['cart_abandoned', 'browse_interest', 'inactivity', 'points_expiry', 'festival', 'payday', 'welcome', 'campaign']
const QUICK: PolicyName[] = ['cart_abandoner', 'vip', 'deal_hunter', 'at_risk', 'new_user', 'high_returner']
const STEP_MS = 450

export function Playground() {
  const [params, setParams] = useSearchParams()
  const customerId = params.get('customer') ?? ''
  const trigger = (params.get('trigger') as TriggerType | null) ?? 'cart_abandoned'
  const [when, setWhen] = useState('') // datetime-local, IST
  const [forceFail, setForceFail] = useState(false)
  const [shown, setShown] = useState(0)
  const [ranForced, setRanForced] = useState(false)

  const set = (k: string, v: string) => setParams((p) => { if (v) p.set(k, v); else p.delete(k); return p }, { replace: true })

  const run = useMutation({
    mutationFn: () =>
      api.playground({
        customer_id: customerId,
        trigger,
        // Asks the harness to skip the LLM for this dry run (CR-D3); the env flag does the same server-wide.
        meta: forceFail ? { force_llm_fail: true, initiated_by: 'admin' } : { initiated_by: 'admin' },
        now: when ? `${when}:00+05:30` : undefined,
      }),
    onMutate: () => {
      setShown(0)
      setRanForced(forceFail)
    },
  })
  const d = run.data
  const steps = d ? buildSteps(d) : []

  // Reveal the pipeline one stage at a time so the audience can follow it.
  useEffect(() => {
    if (!d || shown >= steps.length) return
    const t = setTimeout(() => setShown((n) => n + 1), shown === 0 ? 50 : STEP_MS)
    return () => clearTimeout(t)
  }, [d, shown, steps.length])

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 md:p-6">
      <PageHeader title="Playground" why={NAV[7].why} />

      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <aside className="space-y-4 self-start rounded-[8px] border border-line bg-surface p-4 lg:sticky lg:top-4">
          <CustomerPicker value={customerId} onChange={(v) => set('customer', v)} />

          <label className="block space-y-1">
            <span className="text-[12px] font-medium text-muted">Trigger</span>
            <select
              value={trigger}
              onChange={(e) => set('trigger', e.target.value)}
              className="h-8 w-full rounded-[6px] border border-line bg-surface px-2 text-[13px] text-ink focus-visible:border-ink focus-visible:outline-none"
            >
              {TRIGGERS.map((t) => <option key={t} value={t}>{TRIGGER_LABEL[t]}</option>)}
            </select>
          </label>

          <label className="block space-y-1">
            <span className="text-[12px] font-medium text-muted">Time travel (IST, optional)</span>
            <Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
            <span className="flex flex-wrap gap-1">
              {[['Dhanteras eve', '2026-11-05T19:00'], ['Diwali', '2026-11-08T11:00'], ['Late night', '2026-10-25T23:30']].map(([l, v]) => (
                <button key={l} type="button" onClick={() => setWhen(v)} className="rounded-[5px] border border-line px-1.5 py-0.5 text-[11.5px] text-muted hover:text-ink">
                  {l}
                </button>
              ))}
              {when ? <button type="button" onClick={() => setWhen('')} className="px-1.5 py-0.5 text-[11.5px] text-muted hover:text-ink">✗ now</button> : null}
            </span>
          </label>

          <div className="flex items-center justify-between gap-2">
            <span className="text-[13px]">
              Force LLM failure
              <span className="block text-[11.5px] text-muted">Proves the rules fallback still decides safely.</span>
            </span>
            <Switch checked={forceFail} onChange={setForceFail} label="Force LLM failure" />
          </div>

          <Button variant="primary" className="w-full" disabled={!customerId || run.isPending} onClick={() => run.mutate()}>
            <Play /> {run.isPending ? 'Running the pipeline…' : 'Run (dry run, nothing is sent)'}
          </Button>
        </aside>

        <section aria-label="Pipeline trace" aria-live="polite" className="dot-grid min-h-[520px] rounded-[8px] border border-line bg-bg p-4 md:p-6">
          {!d && !run.isPending ? (
            <EmptyState
              className="border-none bg-transparent"
              title="Pick a customer and press Run"
              hint="The full decision pipeline runs live (pre-gate, policy, AI agent, validator) but nothing is sent or logged."
              action={<span className="text-[12px] text-muted">Tip: ⌘K → “Run Playground for…”</span>}
            />
          ) : run.isPending ? (
            <div className="space-y-3">
              {[0, 1, 2, 3].map((i) => <div key={i} className="h-14 animate-pulse rounded-[8px] bg-surface-2" />)}
              <p className="text-[12px] text-muted">The AI agent can take a few seconds…</p>
            </div>
          ) : d ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <PipelineLens decision={{ decided_by: d.decided_by, status: d.status, fallback_reason: d.fallback_reason, explanation_title: d.explanation.title }} />
                <Button size="sm" variant="ghost" onClick={() => setShown(0)}><RotateCcw /> Replay</Button>
              </div>
              <ForceFailNote d={d} requested={ranForced} />
              <ol>
                {steps.slice(0, shown).map((s, i) => <StepView key={s.key} step={s} index={i} last={i === steps.length - 1} />)}
              </ol>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  )
}

function ForceFailNote({ d, requested }: { d: Decision; requested: boolean }) {
  if (!requested || d.decided_by === 'RULES_FALLBACK' || d.decided_by === 'BLOCKED_PREGATE' || d.decided_by === 'HOLDOUT') return null
  return (
    <p className="rounded-[6px] border border-amber/50 bg-amber-soft px-3 py-2 text-[12.5px] text-amber-text">
      ⚠ The API ignored “force LLM failure” for this run, so the AI still decided. Per-run forcing needs a small backend change (CR-D3); until then
      it only works with FORCE_LLM_FAIL on the server.
    </p>
  )
}

function CustomerPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [q, setQ] = useState(value)
  const [open, setOpen] = useState(false)
  const results = useQuery({
    queryKey: ['customers', 'picker', q],
    queryFn: () => api.customers({ q: q || undefined, limit: 8 }),
    enabled: open,
    placeholderData: keepPreviousData,
  })
  const quick = useMutation({
    mutationFn: (policy: PolicyName) => api.customers({ policy, limit: 1 }),
    onSuccess: (r) => {
      const c = r.items[0]
      if (c) { onChange(c.customer_id); setQ(c.customer_id) }
    },
  })
  return (
    <div className="space-y-1.5">
      <label htmlFor="pg-customer" className="text-[12px] font-medium text-muted">Customer</label>
      <div className="relative">
        <Input
          id="pg-customer"
          value={q}
          placeholder="Name or ID (C000123, TG…)"
          autoComplete="off"
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onChange={(e) => { setQ(e.target.value); setOpen(true) }}
        />
        {open && results.data?.items.length ? (
          <ul role="listbox" className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-[6px] border border-line bg-surface py-1 shadow-menu">
            {results.data.items.map((c) => (
              <li key={c.customer_id} role="option" aria-selected={c.customer_id === value}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { onChange(c.customer_id); setQ(c.customer_id); setOpen(false) }}
                  className={cn('flex w-full items-center justify-between gap-2 px-2.5 py-1.5 text-left text-[13px] hover:bg-surface-2', c.customer_id === value && 'bg-surface-2')}
                >
                  <span>{c.first_name} <span className="num text-[11.5px] text-muted">{c.customer_id}</span></span>
                  <span className="text-[11.5px] text-muted">{POLICY_LABEL[c.policy]}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-1" aria-label="Quick pick a customer by policy">
        {QUICK.map((p) => (
          <button
            key={p}
            type="button"
            disabled={quick.isPending}
            onClick={() => quick.mutate(p)}
            className="rounded-[5px] border border-line px-1.5 py-0.5 text-[11.5px] text-muted hover:text-ink"
          >
            {POLICY_LABEL[p]}
          </button>
        ))}
      </div>
    </div>
  )
}
