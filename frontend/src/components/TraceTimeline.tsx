import type { Decision } from '@/lib/types'
import { cn, formatInt } from '@/lib/utils'

/** Each agent tool call with its duration; a bar shows where the time went. */
export function TraceTimeline({ d }: { d: Decision }) {
  const trace = d.agent_trace
  if (!trace.length)
    return (
      <p className="rounded-[8px] border border-dashed border-line px-4 py-4 text-[13px] text-muted">
        {d.decided_by === 'BLOCKED_PREGATE'
          ? 'The AI was never called: the pre-gate stopped this decision first.'
          : d.decided_by === 'HOLDOUT'
            ? 'The AI was never called: this customer is in the holdout group.'
            : 'No tool calls were recorded for this decision.'}
      </p>
    )
  const max = Math.max(...trace.map((t) => t.ms))
  return (
    <div className="space-y-2">
      <ol className="relative space-y-3 border-l border-line pl-4">
        {trace.map((t, i) => {
          const failed = /violation|timeout|error|fail/i.test(t.result_summary)
          return (
            <li key={i} className="relative">
              <span
                aria-hidden
                className={cn('absolute -left-[21px] top-1 size-2.5 rounded-full border-2 border-bg', failed ? 'bg-danger' : 'bg-ink')}
              />
              <div className="flex items-baseline justify-between gap-3">
                <span className="num text-[12.5px] text-ink">
                  {i + 1}. {t.name}
                </span>
                <span className="num text-[11.5px] text-muted">{formatInt(t.ms)} ms</span>
              </div>
              <p className={cn('text-[12.5px]', failed ? 'text-danger-text' : 'text-muted')}>
                {failed ? '✗ ' : '✓ '}
                {t.result_summary}
              </p>
              <div className="mt-1 h-1 rounded-full bg-surface-2" aria-hidden>
                <div className={cn('h-full rounded-full', failed ? 'bg-danger/70' : 'bg-slate')} style={{ width: `${Math.max(2, (t.ms / max) * 100)}%` }} />
              </div>
            </li>
          )
        })}
      </ol>
      <p className="num text-[11.5px] text-muted">
        {trace.length} tool calls · {formatInt(d.llm_tokens)} tokens · {(d.latency_ms / 1000).toFixed(1)} s total
        {d.fallback_reason ? ` · fallback: ${d.fallback_reason}` : ''}
      </p>
    </div>
  )
}
