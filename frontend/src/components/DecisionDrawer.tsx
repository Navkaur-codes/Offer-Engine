import * as D from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { Check, Link2, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { useDecisionParam } from '@/lib/decisionParam'
import { festivalLabel } from '@/lib/festivals'
import { PHASE_LABEL, TRIGGER_LABEL } from '@/lib/labels'
import type { Decision } from '@/lib/types'
import { formatDateTime, formatInt } from '@/lib/utils'
import { OutcomeBadge } from './badges'
import { EmptyState } from './EmptyState'
import { ExplanationCard } from './ExplanationCard'
import { Money } from './Money'
import { ProfileSnapshot } from './ProfileSnapshot'
import { RuleCheckList } from './RuleCheckList'
import { TelegramPreview } from './TelegramPreview'
import { TraceTimeline } from './TraceTimeline'
import { Button } from './ui/button'

/** Global decision drawer, opened from anywhere via `?decision=<id>`. */
export function DecisionDrawer() {
  const { id, close } = useDecisionParam()
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy the link', { description: window.location.href })
    }
  }

  return (
    <D.Root open={Boolean(id)} onOpenChange={(v) => !v && close()}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-40 bg-black/30" />
        <D.Content className="fixed inset-y-0 right-0 z-50 flex w-[min(100vw,600px)] flex-col border-l border-line bg-bg shadow-menu focus:outline-none">
          <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-line bg-surface px-4">
            <D.Title className="num truncate text-[13px] text-ink">{id}</D.Title>
            <D.Description className="sr-only">Why this decision was made: explanation, message, agent trace, rule checks and customer profile</D.Description>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={copy} aria-label="Copy link to this decision">
                {copied ? <Check /> : <Link2 />}
                {copied ? 'Copied' : 'Copy link'}
              </Button>
              <D.Close className="rounded-[6px] p-1.5 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Close">
                <X className="size-4" />
              </D.Close>
            </div>
          </div>
          {id ? <Detail id={id} /> : null}
        </D.Content>
      </D.Portal>
    </D.Root>
  )
}

function Detail({ id }: { id: string }) {
  const { data: d, isLoading, isError } = useQuery({ queryKey: ['decision', id], queryFn: () => api.decision(id), retry: false })
  if (isLoading)
    return (
      <div className="space-y-3 p-4">
        <div className="h-48 animate-pulse rounded-[8px] bg-surface-2" />
        <div className="h-24 animate-pulse rounded-[8px] bg-surface-2" />
      </div>
    )
  if (isError || !d)
    return (
      <EmptyState
        className="m-4"
        title="Decision not found"
        hint={`There is no decision with ID ${id}. Check the ID, or pick one from the Decisions table.`}
        action={<D.Close asChild><Button>Close</Button></D.Close>}
      />
    )
  return <Body d={d} />
}

function Body({ d }: { d: Decision }) {
  return (
    <div className="flex-1 space-y-5 overflow-y-auto p-4">
      <p className="num text-[12px] text-muted">
        {formatDateTime(d.ts)} · {TRIGGER_LABEL[d.trigger]}
        {d.context.festival ? ` · ${festivalLabel(d.context.festival)}${d.context.festival_phase ? ` ${PHASE_LABEL[d.context.festival_phase]}` : ''}` : ''}
      </p>
      <ExplanationCard explanation={d.explanation} decidedBy={d.decided_by} status={d.status} fallbackReason={d.fallback_reason} />

      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat term="Cost"><Money value={d.cost} /></Stat>
        <Stat term="Expected incr. profit"><Money value={d.expected_incremental_profit} /></Stat>
        <Stat term="Outcome"><OutcomeBadge outcome={d.outcome} /></Stat>
        <Stat term="Revenue">{d.revenue !== null ? <Money value={d.revenue} /> : <span className="text-muted">—</span>}</Stat>
      </dl>

      <Section title="Message the customer got">
        <TelegramPreview d={d} />
      </Section>

      <Section title="Agent trace" note="Every tool the AI called, in order. The agent can only read, never write.">
        <TraceTimeline d={d} />
      </Section>

      {d.candidates.length ? (
        <Section title="Offers it could choose from" note="Already limited by Global → Festival → Persona → Individual rules.">
          <ul className="divide-y divide-line rounded-[8px] border border-line bg-surface text-[12.5px]">
            {d.candidates.map((c) => (
              <li key={c.offer_id} className="flex items-center justify-between gap-3 px-3 py-2">
                <div className="min-w-0">
                  <p className="num text-ink">
                    {c.offer_id === d.final_offer_id ? '● ' : ''}
                    {c.offer_id}
                  </p>
                  <p className="truncate text-muted">{c.rule_notes.join(' · ')}</p>
                </div>
                <span className="num shrink-0 text-right text-muted">
                  cost <Money value={c.est_cost} /> · profit <Money value={c.est_incremental_profit} />
                </span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Section title="Rule checks" note="The final validator re-runs rules.evaluate() on the exact offer before sending.">
        {d.validation ? (
          <RuleCheckList checks={d.validation.checks} />
        ) : (
          <p className="rounded-[8px] border border-danger/40 bg-danger-soft px-3 py-2 text-[13px] text-danger-text">
            ✗ Stopped before validation: {d.explanation.title.replace(/^Blocked: /, '')}
          </p>
        )}
        <ul className="mt-2 space-y-0.5 text-[12px] text-muted">
          {d.effective_policy.summary.map((s) => <li key={s}>· {s}</li>)}
        </ul>
        <p className="num mt-1 text-[11px] text-muted">policy hash {d.effective_policy.version_hash} · {formatInt(d.effective_policy.rules.length)} rules merged</p>
      </Section>

      <Section title="Customer at decision time">
        <ProfileSnapshot p={d.profile_snapshot} />
      </Section>
    </div>
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

function Stat({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="rounded-[8px] border border-line bg-surface p-2.5">
      <dt className="text-[11px] text-muted">{term}</dt>
      <dd className="mt-1 text-[14px] text-ink">{children}</dd>
    </div>
  )
}
