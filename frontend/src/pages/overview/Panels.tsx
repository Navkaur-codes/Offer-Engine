import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Money } from '@/components/Money'
import { Button } from '@/components/ui/button'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card'
import { usePasscode } from '@/lib/hooks'
import { Countdown } from '@/app/topbar/UpcomingMoments'
import { api } from '@/lib/api'
import { useUpcoming } from '@/lib/festivals'
import { DECIDED_BY_LABEL, PHASE_LABEL } from '@/lib/labels'
import type { DecidedBy, DecisionLight, JobResult, Kpis } from '@/lib/types'
import { cn, formatDate, formatDateTime, formatInt, formatPct } from '@/lib/utils'
import { PicksReport } from './PicksReport'

/** sent → claimed → redeemed, from the most recent decisions. */
export function Funnel({ decisions, className }: { decisions: DecisionLight[]; className?: string }) {
  const sent = decisions.filter((d) => d.status === 'SENT')
  const claimed = sent.filter((d) => d.outcome === 'claimed' || d.outcome === 'redeemed').length
  const redeemed = sent.filter((d) => d.outcome === 'redeemed').length
  const steps = [
    { label: 'Sent', n: sent.length, note: '' },
    { label: 'Claimed', n: claimed, note: sent.length ? `${formatPct(claimed / sent.length, 0)} of sent` : '' },
    { label: 'Redeemed', n: redeemed, note: claimed ? `${formatPct(redeemed / claimed, 0)} of claimed` : '' },
  ]
  const max = Math.max(1, sent.length)
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Offer funnel</CardTitle>
        <span className="text-[11.5px] text-muted">last {decisions.length} decisions</span>
      </CardHeader>
      <CardBody className="space-y-3">
        {steps.map((s) => (
          <div key={s.label} className="space-y-1 text-[13px]">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-muted">{s.label}</span>
              <span className="num whitespace-nowrap">
                <span className="text-ink">{formatInt(s.n)}</span>
                {s.note ? <span className="text-[11.5px] text-muted"> · {s.note}</span> : null}
              </span>
            </div>
            <div className="h-4 rounded-[4px] bg-surface-2" aria-hidden>
              <div className="h-full rounded-[4px] bg-slate" style={{ width: `${(s.n / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  )
}

const BY_ORDER: DecidedBy[] = ['AGENT', 'AGENT_RETRY', 'RULES_FALLBACK', 'BLOCKED_PREGATE', 'HOLDOUT']
const BY_BAR: Record<DecidedBy, string> = {
  AGENT: 'bg-signal', AGENT_RETRY: 'bg-signal/60', RULES_FALLBACK: 'bg-violet', BLOCKED_PREGATE: 'bg-danger/70', HOLDOUT: 'bg-slate/50',
}

/** Who made each decision. A 100% bar, never a donut (T08). */
export function DecidedByShare({ kpis, decisions, className }: { kpis?: Kpis; decisions: DecisionLight[]; className?: string }) {
  const counts = BY_ORDER.map((by) => ({ by, n: decisions.filter((d) => d.decided_by === by).length }))
  const total = Math.max(1, decisions.length)
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Who decided</CardTitle>
      </CardHeader>
      <CardBody className="space-y-3">
        <div className="flex h-3 overflow-hidden rounded-[4px]" aria-hidden>
          {counts.map((c) => (c.n ? <div key={c.by} className={BY_BAR[c.by]} style={{ width: `${(c.n / total) * 100}%` }} /> : null))}
        </div>
        <ul className="space-y-1 text-[12.5px]">
          {counts.map((c) => (
            <li key={c.by} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <span aria-hidden className={cn('size-2 rounded-[2px]', BY_BAR[c.by])} />
                {DECIDED_BY_LABEL[c.by]}
              </span>
              <span className="num text-muted">
                {c.n} · {formatPct(c.n / total, 0)}
              </span>
            </li>
          ))}
        </ul>
        <p className="text-[12px] text-muted">
          {kpis ? <>Today: agent <span className="num text-ink">{formatPct(kpis.agent_share, 0)}</span>, fallback <span className="num text-ink">{formatPct(kpis.fallback_share, 0)}</span>. </> : null}
          The rules fallback steps in whenever the AI is slow or wrong, so sending never depends on the LLM.
        </p>
      </CardBody>
    </Card>
  )
}

export function DigestCard({ className }: { className?: string }) {
  const { data, isLoading } = useQuery({ queryKey: ['digest'], queryFn: () => api.digest() })
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Today’s AI digest</CardTitle>
        {data ? <span className="num text-[11.5px] text-muted">{formatDate(data.day)} · by {data.generated_by}</span> : null}
      </CardHeader>
      <CardBody>
        {isLoading ? (
          <div className="space-y-2">
            <div className="h-3 w-full animate-pulse rounded bg-surface-2" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-surface-2" />
          </div>
        ) : (
          <p className="text-[13.5px] leading-relaxed text-ink">{data?.text ?? 'No digest yet for today.'}</p>
        )}
      </CardBody>
    </Card>
  )
}

export function MarginCallout({ kpis, className }: { kpis?: Kpis; className?: string }) {
  const { data: today } = useQuery({ queryKey: ['today'], queryFn: api.today, refetchInterval: 30_000 })
  return (
    <Card className={cn('flex flex-col justify-between p-4', className)}>
      <div className="space-y-1">
        <p className="text-[12px] font-medium text-muted">Margin protected by not discounting sure-things · last 12 months</p>
        <p className="num title text-[28px] leading-none text-ink">{kpis ? <Money value={kpis.margin_saved} /> : '…'}</p>
      </div>
      <p className="mt-3 text-[12.5px] text-muted">
        {today ? (
          <>
            Today: <Money value={today.margin_kept} className="text-ink" /> kept by sending nothing to{' '}
            <span className="num text-ink">{formatInt(today.no_offer)}</span> customer{today.no_offer === 1 ? '' : 's'} ·{' '}
            <Money value={today.spent} className="text-ink" /> spent on <span className="num text-ink">{formatInt(today.sent)}</span> offer{today.sent === 1 ? '' : 's'}.{' '}
          </>
        ) : null}
        <Link to="/experiments" className="text-ink underline-offset-2 hover:underline">See the proof →</Link>
      </p>
    </Card>
  )
}

export function MomentsStrip({ className }: { className?: string }) {
  const list = useUpcoming().filter((x) => x.days >= 0).slice(0, 4)
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Upcoming moments</CardTitle>
        <Link to="/festivals" className="text-[12.5px] text-muted hover:text-ink">Calendar →</Link>
      </CardHeader>
      <ul className="grid grid-cols-1 divide-y divide-line sm:grid-cols-2 sm:divide-y-0">
        {list.map(({ f, days, phase }) => (
          <li key={f.id} className="space-y-1 px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[13px] text-ink">{f.name}</span>
              <Countdown days={days} />
            </div>
            <p className="num text-[11.5px] text-muted">
              {formatDate(f.date)}
              {phase ? ` · ${PHASE_LABEL[phase]}` : ' · not started'} · pool <Money value={f.budget} compact />
            </p>
          </li>
        ))}
      </ul>
    </Card>
  )
}

// Plain-English description of each proactive job: what it does and who it targets.
const JOBS: Record<string, { label: string; what: string; empty: string }> = {
  cart_abandonment: {
    label: 'Abandoned carts',
    what: 'Every 5 min: nudges Telegram customers whose cart is 30 min – 6 h old, unbought and not yet nudged.',
    empty: 'nothing due right now (only Telegram customers with a 30 min – 6 h old cart)',
  },
  flush_quiet_queue: {
    label: 'Queued offers',
    what: '09:05 IST: re-decides offers that quiet hours (21:00–09:00) held overnight, under today’s rules and consent.',
    empty: 'nothing queued from last night',
  },
  personal_picks: {
    label: 'Personal picks',
    what: '11:00 + 18:00 IST: one offer per Telegram and Lab customer, built on their own profile (top category, policy, uplift). Lab picks post in the Lab group.',
    empty: 'no Telegram or Lab customers to pick for yet',
  },
  points_expiry: {
    label: 'Points expiry',
    what: '10:00 IST: reminds Telegram customers whose points expire within 3 days (at most once per 3 days).',
    empty: 'no Telegram customer has points expiring in the next 3 days',
  },
  daily_digest: {
    label: 'Daily digest',
    what: '21:00 IST: sends the day’s plain-English summary to the admins on Telegram.',
    empty: 'no admin received it',
  },
}
const jobLabel = (job: string) => JOBS[job]?.label ?? job.replaceAll('_', ' ')

/** Turns the runner's summary into one honest sentence (it never claims work that didn't happen). */
function reportJob(job: string, r: JobResult) {
  const name = jobLabel(job)
  if (r.error) {
    toast.error(`${name}: failed`, { description: `The job raised ${r.error}. Nothing was sent.` })
    return
  }
  if (r.admins_messaged !== undefined) {
    toast(r.admins_messaged
      ? `${name} sent to ${r.admins_messaged} admin${r.admins_messaged === 1 ? '' : 's'} on Telegram`
      : `${name}: ${JOBS[job]?.empty ?? 'nothing sent'}`)
    return
  }
  if (!r.decisions) {
    toast(`${name}: ${JOBS[job]?.empty ?? 'nothing due right now'}`)
    return
  }
  toast(`${name}: ${r.decisions} decision${r.decisions === 1 ? '' : 's'} · ${r.sent ?? 0} sent · ${r.queued ?? 0} queued`, {
    description: 'Every one is in the Decisions log with its reason.',
  })
}

/** Proactive triggers the scheduler runs on its own; admins can run one now for a demo. */
export function AutomationsCard({ className }: { className?: string }) {
  const qc = useQueryClient()
  const { unlocked } = usePasscode()
  const { data } = useQuery({ queryKey: ['scheduler'], queryFn: api.scheduler, refetchInterval: 60_000 })
  const [report, setReport] = useState<JobResult | null>(null)
  const run = useMutation({
    mutationFn: api.runJob,
    onSuccess: (r, job) => {
      reportJob(job, r)
      if (r.rows) setReport(r)
      for (const key of ['decisions', 'scheduler', 'kpis', 'today', 'budget']) qc.invalidateQueries({ queryKey: [key] })
      // Lab customers react in the group over the next minute; their claims move the claim rate
      if (r.lab_posting) setTimeout(() => ['decisions', 'kpis'].forEach((key) => qc.invalidateQueries({ queryKey: [key] })), 45_000)
    },
  })
  const jobs = Object.entries(data?.next_runs ?? {}).sort((a, b) => (a[1] ?? '~').localeCompare(b[1] ?? '~'))
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Automations</CardTitle>
        <span className="num text-[11.5px] text-muted">{data ? (data.running ? 'scheduler on' : '✗ scheduler off') : '…'}</span>
      </CardHeader>
      {!unlocked ? (
        <p className="border-b border-line bg-amber-soft px-4 py-2 text-[12px] text-amber-text">
          ⚠ Unlock with the admin passcode (top bar) to run jobs now. They also run on their own schedule.
        </p>
      ) : null}
      <ul className="divide-y divide-line">
        {jobs.map(([job, at]) => (
          <li key={job} className="flex items-start justify-between gap-3 px-4 py-2.5 text-[13px]">
            <div className="min-w-0">
              <p className="text-ink">
                {jobLabel(job)} <span className="num text-[11.5px] text-muted">· {at ? `next ${formatDateTime(at)}` : 'paused'}</span>
              </p>
              {JOBS[job] ? <p className="text-[12px] text-muted">{JOBS[job].what}</p> : null}
            </div>
            <Button
              size="sm"
              variant="secondary"
              className="shrink-0"
              disabled={!unlocked || run.isPending}
              onClick={() => run.mutate(job)}
              aria-label={`Run ${jobLabel(job)} now`}
            >
              <Play /> {run.isPending && run.variables === job ? 'Running…' : 'Run now'}
            </Button>
          </li>
        ))}
        {data && !jobs.length ? <li className="px-4 py-3 text-[13px] text-muted">No scheduled jobs.</li> : null}
      </ul>
      <PicksReport result={report} onClose={() => setReport(null)} />
    </Card>
  )
}
