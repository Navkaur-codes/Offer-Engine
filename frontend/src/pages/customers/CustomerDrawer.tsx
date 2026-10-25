import * as D from '@radix-ui/react-dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, X, Zap } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { DecidedByBadge, StatusBadge } from '@/components/badges'
import { EmptyState } from '@/components/EmptyState'
import { ExplanationCard } from '@/components/ExplanationCard'
import { ProfileSnapshot } from '@/components/ProfileSnapshot'
import { TelegramPreview } from '@/components/TelegramPreview'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useDecisionParam } from '@/lib/decisionParam'
import { usePasscode } from '@/lib/hooks'
import { TRIGGER_LABEL } from '@/lib/labels'
import type { Decision, Event, EventType, TriggerType } from '@/lib/types'
import { formatDateTime, formatInr } from '@/lib/utils'

const SIM_TRIGGERS: TriggerType[] = ['cart_abandoned', 'browse_interest', 'inactivity', 'points_expiry', 'festival', 'payday']

const EVENT_LABEL: Record<EventType, [string, string]> = {
  session: ['○', 'Visited'], view: ['◦', 'Viewed'], add_to_cart: ['+', 'Added to cart'], checkout_started: ['→', 'Started checkout'],
  purchase: ['₹', 'Bought'], return: ['↩', 'Returned'], wishlist: ['♡', 'Wishlisted'], offer_received: ['✉', 'Got an offer'],
  offer_claimed: ['✓', 'Claimed an offer'], offer_declined: ['✗', 'Declined an offer'],
}

export function CustomerDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  return (
    <D.Root open={Boolean(id)} onOpenChange={(v) => !v && onClose()}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-40 bg-black/30" />
        <D.Content className="fixed inset-y-0 right-0 z-40 flex w-[min(100vw,600px)] flex-col border-l border-line bg-bg shadow-menu focus:outline-none">
          <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-line bg-surface px-4">
            <D.Title className="num truncate text-[13px] text-ink">{id}</D.Title>
            <D.Description className="sr-only">Customer profile, recent activity, past decisions and actions</D.Description>
            <D.Close className="rounded-[6px] p-1.5 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Close">
              <X className="size-4" />
            </D.Close>
          </div>
          {id ? <Body id={id} /> : null}
        </D.Content>
      </D.Portal>
    </D.Root>
  )
}

function Body({ id }: { id: string }) {
  const qc = useQueryClient()
  const { unlocked } = usePasscode()
  const { open: openDecision } = useDecisionParam()
  const [trigger, setTrigger] = useState<TriggerType>('cart_abandoned')
  const detail = useQuery({ queryKey: ['customer', id], queryFn: () => api.customer(id), retry: false })
  const dryRun = useMutation({ mutationFn: () => api.playground({ customer_id: id, trigger }) })
  const simulate = useMutation({
    mutationFn: (t: TriggerType) => api.simulate(id, t, { initiated_by: 'admin' }),
    onSuccess: (d) => {
      toast(d.explanation.title, { description: `${TRIGGER_LABEL[d.trigger]} · logged as ${d.id}`, action: { label: 'Open', onClick: () => openDecision(d.id) } })
      qc.invalidateQueries({ queryKey: ['customer', id] })
      qc.invalidateQueries({ queryKey: ['decisions'] })
    },
  })

  if (detail.isLoading) return <div className="m-4 h-64 animate-pulse rounded-[8px] bg-surface-2" />
  if (detail.isError || !detail.data)
    return <EmptyState className="m-4" title="Customer not found" hint={`No customer with ID ${id}.`} action={<D.Close asChild><Button>Close</Button></D.Close>} />

  const { profile, events, decisions } = detail.data
  const realPerson = profile.customer_id.startsWith('TG')

  return (
    <div className="flex-1 space-y-5 overflow-y-auto p-4">
      <Section title="What would the engine do now?" note="A dry run: the full pipeline runs, but nothing is sent or logged.">
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative">
            <span className="sr-only">Trigger</span>
            <select
              value={trigger}
              onChange={(e) => setTrigger(e.target.value as TriggerType)}
              className="h-8 appearance-none rounded-[6px] border border-line bg-surface pl-2.5 pr-7 text-[13px] text-ink focus-visible:border-ink focus-visible:outline-none"
            >
              {SIM_TRIGGERS.map((t) => <option key={t} value={t}>{TRIGGER_LABEL[t]}</option>)}
            </select>
            <span aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-muted">▼</span>
          </label>
          <Button variant="primary" onClick={() => dryRun.mutate()} disabled={dryRun.isPending}>
            <Play /> {dryRun.isPending ? 'Running…' : 'Run decision now'}
          </Button>
        </div>
        {dryRun.data ? <DryRunResult d={dryRun.data} /> : null}
      </Section>

      <Section
        title="Simulate a trigger"
        note={realPerson
          ? '⚠ This is a real Telegram user: a simulated trigger runs the live pipeline and can message them.'
          : 'Runs the live pipeline for this synthetic customer and logs the decision (like /simulate in the bot).'}
      >
        <div className="flex flex-wrap gap-1.5">
          {SIM_TRIGGERS.map((t) => (
            <Button
              key={t}
              size="sm"
              disabled={!unlocked || simulate.isPending}
              title={unlocked ? undefined : 'Unlock edits with the admin passcode first'}
              onClick={() => {
                if (realPerson && !window.confirm(`Send a real "${TRIGGER_LABEL[t]}" decision to ${profile.first_name} on Telegram?`)) return
                simulate.mutate(t)
              }}
            >
              <Zap /> {TRIGGER_LABEL[t]}
            </Button>
          ))}
        </div>
        {!unlocked ? <p className="text-[12px] text-amber-text">⚠ Unlock edits with the admin passcode (top bar) to simulate.</p> : null}
      </Section>

      <Section title="Profile in plain words">
        <ProfileSnapshot p={profile} />
      </Section>

      <Section title="Past decisions" note="Newest first. Click one to see why.">
        {decisions.length ? (
          <ul className="divide-y divide-line rounded-[8px] border border-line bg-surface">
            {decisions.map((d) => (
              <li key={d.id}>
                <button onClick={() => openDecision(d.id)} className="flex w-full items-center gap-3 px-3 py-2 text-left text-[12.5px] hover:bg-surface-2">
                  <span className="num w-24 shrink-0 text-muted">{formatDateTime(d.ts)}</span>
                  <span className="min-w-0 flex-1 truncate text-ink">{d.explanation_title}</span>
                  <StatusBadge status={d.status} />
                  <DecidedByBadge by={d.decided_by} />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded-[8px] border border-dashed border-line px-3 py-4 text-[13px] text-muted">No decisions for this customer yet. Run one above.</p>
        )}
      </Section>

      <Section title="Recent activity" note={`Last ${events.length} events from the synthetic shopping history.`}>
        <Timeline events={events} />
      </Section>
    </div>
  )
}

function DryRunResult({ d }: { d: Decision }) {
  return (
    <div className="space-y-3">
      <ExplanationCard explanation={d.explanation} decidedBy={d.decided_by} status={d.status} fallbackReason={d.fallback_reason} />
      {d.message ? <TelegramPreview d={d} /> : null}
    </div>
  )
}

function Timeline({ events }: { events: Event[] }) {
  if (!events.length) return <p className="text-[13px] text-muted">No events recorded.</p>
  return (
    <ol className="space-y-1.5 border-l border-line pl-4">
      {events.slice(0, 25).map((e) => {
        const [glyph, label] = EVENT_LABEL[e.type]
        return (
          <li key={e.id} className="relative text-[12.5px]">
            <span aria-hidden className="num absolute -left-[22px] top-0 w-3 bg-bg text-center text-muted">{glyph}</span>
            <span className="num mr-2 text-muted">{formatDateTime(e.ts)}</span>
            <span className="text-ink">{label}</span>
            {e.item ? <span className="text-muted"> · {e.item}</span> : e.category ? <span className="text-muted"> · {e.category.replace('_', ' ')}</span> : null}
            {e.value ? <span className="num text-muted"> · {formatInr(e.value)}</span> : null}
          </li>
        )
      })}
    </ol>
  )
}

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <div>
        <h3 className="title text-[13px] text-ink">{title}</h3>
        {note ? <p className="text-[12px] text-muted">{note}</p> : null}
      </div>
      {children}
    </section>
  )
}
