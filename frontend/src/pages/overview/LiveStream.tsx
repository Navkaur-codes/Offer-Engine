import { Pause, Play } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useDecisionParam } from '@/lib/decisionParam'
import { DECIDED_BY_LABEL, POLICY_LABEL } from '@/lib/labels'
import { useDecisionStream } from '@/lib/stream'
import type { DecidedBy, DecisionStatus } from '@/lib/types'
import { cn, formatInr } from '@/lib/utils'

const GLYPH: Record<DecisionStatus, string> = { SENT: '✓', QUEUED: '⏱', NO_OFFER: '–', BLOCKED: '✗', HELD_OUT: '◌', DRY_RUN: '▷' }
const BY_CLASS: Record<DecidedBy, string> = {
  AGENT: 'text-signal-text', AGENT_RETRY: 'text-signal-text', RULES_FALLBACK: 'text-violet-text',
  BLOCKED_PREGATE: 'text-danger-text', HOLDOUT: 'text-muted',
}
const timeFmt = new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

/** Terminal-style feed. Always dark (scoped `.dark`), mono, newest on top. */
export function LiveStream({ className }: { className?: string }) {
  const { items, mode, loading, paused, setPaused } = useDecisionStream(24)
  const { open } = useDecisionParam()

  return (
    <section aria-label="Live decision stream" className={cn('dark flex min-h-0 flex-col overflow-hidden rounded-[8px] border border-line bg-bg text-ink', className)}>
      <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <h2 className="title text-[13px]">Live decisions</h2>
        <div className="flex items-center gap-3">
          <span className="num flex items-center gap-1.5 text-[11.5px] text-muted" role="status">
            <span aria-hidden className={cn('size-1.5 rounded-full', mode === 'paused' ? 'bg-muted' : 'animate-pulse bg-signal')} />
            {mode === 'sse' ? 'live' : mode === 'polling' ? 'live · polling 5 s' : 'paused'}
          </span>
          <button
            onClick={() => setPaused(!paused)}
            className="rounded-[6px] p-1 text-muted hover:bg-surface-2 hover:text-ink"
            aria-label={paused ? 'Resume live stream' : 'Pause live stream'}
          >
            {paused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />}
          </button>
        </div>
      </header>
      <ol className="num min-h-0 flex-1 overflow-y-auto py-1 text-[12px] leading-5">
        {loading
          ? Array.from({ length: 8 }, (_, i) => <li key={i} className="mx-4 my-2 h-3 animate-pulse rounded bg-surface-2" />)
          : items.map((d) => (
              <li key={d.id} className="row-in">
                <button
                  onClick={() => open(d.id)}
                  className="grid w-full grid-cols-[64px_14px_1fr_auto] items-baseline gap-x-2 px-4 py-1.5 text-left hover:bg-surface-2 focus-visible:bg-surface-2"
                  aria-label={`${d.first_name}: ${d.explanation_title}. Open decision ${d.id}`}
                >
                  <span className="text-muted">{timeFmt.format(new Date(d.ts))}</span>
                  <span aria-hidden className={cn(d.status === 'BLOCKED' ? 'text-danger-text' : d.status === 'QUEUED' ? 'text-amber-text' : 'text-ink')}>
                    {GLYPH[d.status]}
                  </span>
                  <span className="min-w-0 truncate">
                    <span className={BY_CLASS[d.decided_by]}>{DECIDED_BY_LABEL[d.decided_by]}</span>
                    <span className="text-muted"> · </span>
                    <span className="text-ink">{d.first_name}</span>
                    <span className="text-muted"> · {POLICY_LABEL[d.policy]}</span>
                  </span>
                  <span className="text-muted">{d.cost ? formatInr(d.cost) : ''}</span>
                  <span className="col-span-2 col-start-3 truncate font-sans text-[12.5px] text-muted">{d.explanation_title}</span>
                </button>
              </li>
            ))}
      </ol>
      <footer className="border-t border-line px-4 py-2 text-[12px]">
        <Link to="/decisions" className="text-muted hover:text-ink">Filter and search every decision →</Link>
      </footer>
    </section>
  )
}
