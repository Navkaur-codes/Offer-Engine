import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/badges'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { usePasscode } from '@/lib/hooks'
import { PHASE_LABEL } from '@/lib/labels'
import type { Category, Festival, FestivalPhase } from '@/lib/types'
import { cn, formatDate } from '@/lib/utils'

const CATEGORIES: Category[] = ['fashion', 'ethnic_wear', 'electronics', 'beauty', 'home_decor', 'kitchen', 'grocery', 'jewellery', 'gifting', 'winter_wear']
const PHASES: FestivalPhase[] = ['teaser', 'build_up', 'last_minute', 'post']
const catLabel = (c: string) => c.replace('_', ' ').replace(/^./, (s) => s.toUpperCase())

function phaseWindow(f: Festival, p: FestivalPhase): string {
  const w = f.phases[p]
  if (!w) return ''
  const d = (n: number) => (n === 0 ? 'the day' : n < 0 ? `${-n} d before` : `${n} d after`)
  return w[0] === w[1] ? d(w[0]) : `${d(w[0])} → ${d(w[1])}`
}

/** Edits one festival: date, budget, hero categories, per-phase strategy and greeting. Key = id, so it resets per festival. */
export function FestivalEditor({ f }: { f: Festival }) {
  const qc = useQueryClient()
  const { unlocked } = usePasscode()
  const [date, setDate] = useState(f.date)
  const [budget, setBudget] = useState(String(f.budget))
  const [hero, setHero] = useState<Category[]>(f.hero_categories)
  const [strategy, setStrategy] = useState<Partial<Record<FestivalPhase, string>>>(f.strategy)
  const [greeting, setGreeting] = useState(f.greeting ?? '')

  const patch: Partial<Festival> = {}
  if (date !== f.date) patch.date = date
  if (Number(budget) !== f.budget && budget !== '') patch.budget = Number(budget)
  if (hero.join() !== f.hero_categories.join()) patch.hero_categories = hero
  if (PHASES.some((p) => (strategy[p] ?? '') !== (f.strategy[p] ?? ''))) patch.strategy = strategy
  if (greeting !== (f.greeting ?? '') && f.greeting !== null) patch.greeting = greeting
  const dirty = Object.keys(patch).length > 0

  const save = useMutation({
    mutationFn: () => api.updateFestival(f.id, patch),
    onSuccess: (r) => {
      toast(`Saved ${r.name}`, { description: Object.keys(patch).join(', ') })
      qc.invalidateQueries({ queryKey: ['festivals'] })
    },
  })
  const reset = () => {
    setDate(f.date); setBudget(String(f.budget)); setHero(f.hero_categories); setStrategy(f.strategy); setGreeting(f.greeting ?? '')
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="title text-[18px] text-ink">{f.name}</h2>
          <p className="num text-[12px] text-muted">{f.id} · {formatDate(f.date)}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {f.needs_opt_in ? <Badge tone="ink" icon="✓">Greeting: opt-in only</Badge> : <Badge>Commercial sale · no greeting</Badge>}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block space-y-1">
          <span className="text-[12px] font-medium text-muted">Date</span>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="block space-y-1">
          <span className="text-[12px] font-medium text-muted">Festival budget pool (₹)</span>
          <Input className="num" inputMode="numeric" value={budget} onChange={(e) => setBudget(e.target.value.replace(/\D/g, ''))} />
        </label>
      </div>

      <fieldset className="space-y-1.5">
        <legend className="text-[12px] font-medium text-muted">Hero categories (discounts during build-up only go here)</legend>
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => {
            const on = hero.includes(c)
            return (
              <button
                key={c}
                type="button"
                aria-pressed={on}
                onClick={() => setHero(on ? hero.filter((x) => x !== c) : [...hero, c])}
                className={cn('h-7 rounded-[6px] border px-2 text-[12.5px]', on ? 'border-ink bg-ink text-bg' : 'border-line text-muted hover:text-ink')}
              >
                {on ? '✓ ' : ''}{catLabel(c)}
              </button>
            )
          })}
        </div>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-[12px] font-medium text-muted">Strategy per phase (the AI agent reads this)</legend>
        {PHASES.filter((p) => f.phases[p]).map((p) => (
          <label key={p} className="grid gap-1 sm:grid-cols-[150px_1fr] sm:gap-3">
            <span className="pt-1.5 text-[12.5px]">
              <span className="text-ink">{PHASE_LABEL[p].replace(/^./, (s) => s.toUpperCase())}</span>
              <span className="num block text-[11px] text-muted">{phaseWindow(f, p)}</span>
            </span>
            <textarea
              value={strategy[p] ?? ''}
              onChange={(e) => setStrategy({ ...strategy, [p]: e.target.value })}
              rows={2}
              className="w-full resize-y rounded-[6px] border border-line bg-surface px-2.5 py-1.5 text-[13px] text-ink focus-visible:border-ink focus-visible:outline-none"
            />
          </label>
        ))}
      </fieldset>

      <section className="space-y-2">
        <p className="text-[12px] font-medium text-muted">Greeting preview</p>
        {f.greeting !== null ? (
          <div className="grid gap-3 sm:grid-cols-[1fr_260px]">
            <label className="block space-y-1">
              <Input value={greeting} onChange={(e) => setGreeting(e.target.value)} aria-label="Greeting text" />
              <span className="block text-[11.5px] text-muted">
                Sent word for word from this table, never written by the AI. Only customers who opted in to {f.name.split(/[/(]/)[0].trim()} see it; everyone else gets neutral “festive season” wording.
              </span>
            </label>
            <div className="rounded-[8px] border border-line bg-bg p-3">
              <div className="rounded-[10px] rounded-bl-[3px] border border-line bg-surface px-3 py-2 text-[13px] text-ink">
                <p className="font-semibold">{greeting || '—'}, Aditi!</p>
                <p className="text-muted">…offer text follows…</p>
              </div>
              <p className="mt-1.5 text-[11px] text-muted">✓ Opt-in only</p>
            </div>
          </div>
        ) : (
          <p className="rounded-[6px] border border-dashed border-line px-3 py-2 text-[12.5px] text-muted">Commercial sales have no greeting; messages stay neutral for everyone.</p>
        )}
      </section>

      {f.restricted_promos.length ? (
        <p className="text-[12.5px] text-muted">
          <span className="text-danger-text">✗ Never promoted during this festival:</span> {f.restricted_promos.join(', ')} (enforced by the message validator)
        </p>
      ) : null}
      <p className="num text-[11.5px] text-muted">
        Delivery days by city tier: {Object.entries(f.delivery_days_by_tier).map(([t, d]) => `tier ${t} → ${d} d`).join(' · ')}
      </p>

      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-2 border-t border-line bg-surface px-4 py-3">
        <Button variant="primary" disabled={!dirty || !unlocked || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? 'Saving…' : 'Save changes'}
        </Button>
        <Button variant="ghost" disabled={!dirty} onClick={reset}>Discard</Button>
        {!unlocked ? <span className="text-[12px] text-amber-text">⚠ Unlock edits with the admin passcode to save.</span> : dirty ? <span className="text-[12px] text-muted">Unsaved: {Object.keys(patch).join(', ')}</span> : null}
      </div>
    </div>
  )
}
