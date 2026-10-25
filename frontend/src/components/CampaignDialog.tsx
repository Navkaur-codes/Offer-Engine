import { useMutation } from '@tanstack/react-query'
import * as D from '@radix-ui/react-dialog'
import { Play, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { api } from '@/lib/api'
import { festivalKey } from '@/lib/festivals'
import { POLICY_LABEL } from '@/lib/labels'
import { useFestivals } from '@/lib/queries'
import type { PolicyName } from '@/lib/types'
import { cn, formatInt } from '@/lib/utils'
import { DecidedByBadge, PolicyBadge, StatusBadge } from './badges'
import { Money } from './Money'
import { Button } from './ui/button'
import { Input } from './ui/input'

const SELECT = 'h-8 w-full rounded-[6px] border border-line bg-surface px-2 text-[13px] text-ink focus-visible:border-ink focus-visible:outline-none'

/** "Who would get what, at what cost?" before any campaign is sent. Dry run only. */
export function CampaignDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { data: festivals } = useFestivals()
  const [policy, setPolicy] = useState('')
  const [festival, setFestival] = useState('')
  const [budget, setBudget] = useState('20000')
  const [limit, setLimit] = useState('50')
  const run = useMutation({
    mutationFn: () =>
      api.campaignDryRun({
        policy: (policy || undefined) as PolicyName | undefined,
        festival: festival || undefined,
        budget: Math.max(0, Number(budget) || 0),
        limit: Math.min(200, Math.max(1, Number(limit) || 50)),
      }),
  })
  const r = run.data
  const festivalOptions = Object.fromEntries((festivals ?? []).map((f) => [festivalKey(f.id), f.name]))

  // Why customers were skipped, most common first.
  const reasons = new Map<string, number>()
  for (const row of r?.rows ?? []) {
    if (row.final_offer_id) continue
    const why = row.explanation_title.replace(/^[^:]*:\s*/, '')
    reasons.set(why, (reasons.get(why) ?? 0) + 1)
  }

  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <D.Content className="fixed inset-x-0 top-[4vh] z-50 mx-auto flex max-h-[92vh] w-[min(96vw,980px)] flex-col overflow-hidden rounded-[8px] border border-line bg-bg text-ink shadow-menu focus:outline-none">
          <div className="flex items-start justify-between gap-3 border-b border-line bg-surface px-5 py-3">
            <div>
              <D.Title className="title text-[15px]">Campaign dry-run</D.Title>
              <D.Description className="text-[12.5px] text-muted">
                Runs the real engine for a group of customers without sending anything. The AI handles the top 5; rules decide the rest.
              </D.Description>
            </div>
            <D.Close className="rounded-[6px] p-1.5 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Close"><X className="size-4" /></D.Close>
          </div>

          <form
            className="grid gap-3 border-b border-line bg-surface px-5 py-3 sm:grid-cols-[1fr_1fr_140px_110px_auto] sm:items-end"
            onSubmit={(e) => { e.preventDefault(); run.mutate() }}
          >
            <Field label="Policy">
              <select value={policy} onChange={(e) => setPolicy(e.target.value)} className={SELECT}>
                <option value="">All customers</option>
                {Object.entries(POLICY_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
            <Field label="Festival">
              <select value={festival} onChange={(e) => setFestival(e.target.value)} className={SELECT}>
                <option value="">None</option>
                {Object.entries(festivalOptions).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
            <Field label="Budget (₹)">
              <Input inputMode="numeric" value={budget} onChange={(e) => setBudget(e.target.value.replace(/\D/g, ''))} className="num" />
            </Field>
            <Field label="Customers">
              <Input inputMode="numeric" value={limit} onChange={(e) => setLimit(e.target.value.replace(/\D/g, ''))} className="num" />
            </Field>
            <Button type="submit" variant="primary" disabled={run.isPending}>
              <Play /> {run.isPending ? 'Running…' : 'Run dry-run'}
            </Button>
          </form>

          <div className="min-h-[240px] flex-1 overflow-y-auto p-5">
            {run.isPending ? (
              <div className="space-y-2">
                {[0, 1, 2].map((i) => <div key={i} className="h-10 animate-pulse rounded-[6px] bg-surface-2" />)}
                <p className="text-[12px] text-muted">Deciding for every customer; the AI part takes a few seconds…</p>
              </div>
            ) : r ? (
              <div className="space-y-4">
                <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Tile term="Would get an offer">{formatInt(r.totals.would_send)} <span className="text-muted">/ {formatInt(r.totals.customers)}</span></Tile>
                  <Tile term="Total cost"><Money value={r.totals.cost} /> <span className="text-[12px] text-muted">of <Money value={Number(budget) || 0} /></span></Tile>
                  <Tile term="Expected extra profit" strong><Money value={r.totals.expected_incremental_profit} /></Tile>
                  <Tile term="Skipped">
                    {formatInt(r.totals.no_offer)} no offer · {formatInt(r.totals.blocked)} blocked
                    {r.totals.over_budget ? <> · <span className="text-amber-text">{formatInt(r.totals.over_budget)} over budget ⚠</span></> : null}
                  </Tile>
                </dl>

                {reasons.size ? (
                  <div className="rounded-[8px] border border-line bg-surface p-3">
                    <p className="mb-1.5 text-[12px] font-medium text-muted">Why customers got nothing</p>
                    <ul className="space-y-0.5 text-[12.5px]">
                      {[...reasons.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([why, n]) => (
                        <li key={why} className="flex justify-between gap-3"><span className="text-ink">{why}</span><span className="num text-muted">{n}</span></li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <div className="overflow-x-auto rounded-[8px] border border-line bg-surface">
                  <table className="w-full text-[12.5px]">
                    <thead>
                      <tr className="border-b border-line text-left text-[11.5px] text-muted">
                        {['Customer', 'Policy', 'Decision', 'Status', 'Decided by', 'Cost', 'Exp. profit'].map((h) => <th key={h} className="h-8 px-3 font-medium">{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {r.rows.map((d) => (
                        <tr key={d.id} className="border-b border-line last:border-0">
                          <td className="h-9 whitespace-nowrap px-3">{d.first_name} <span className="num text-[11px] text-muted">{d.customer_id}</span></td>
                          <td className="px-3"><PolicyBadge policy={d.policy} /></td>
                          <td className="max-w-[320px] truncate px-3" title={d.explanation_title}>{d.explanation_title}</td>
                          <td className="px-3"><StatusBadge status={d.status} /></td>
                          <td className="px-3"><DecidedByBadge by={d.decided_by} /></td>
                          <td className="px-3"><Money value={d.cost} className="text-muted" /></td>
                          <td className="px-3"><Money value={d.expected_incremental_profit} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="dot-grid rounded-[8px] border border-dashed border-line px-6 py-12 text-center text-[13px] text-muted">
                Choose who to target and a budget, then run. Nothing is sent and nothing is logged.
              </p>
            )}
          </div>
        </D.Content>
      </D.Portal>
    </D.Root>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-[12px] font-medium text-muted">{label}</span>
      {children}
    </label>
  )
}

function Tile({ term, children, strong }: { term: string; children: ReactNode; strong?: boolean }) {
  return (
    <div className="rounded-[8px] border border-line bg-surface p-3">
      <dt className="text-[11.5px] text-muted">{term}</dt>
      <dd className={cn('num mt-1 text-[15px]', strong ? 'title text-ink' : 'text-ink')}>{children}</dd>
    </div>
  )
}
