import type { RuleCheck } from '@/lib/types'
import { cn } from '@/lib/utils'
import { SeverityTag } from './badges'

/** Failed checks first; each row says ✓/✗ in text, not just colour. */
export function RuleCheckList({ checks, className }: { checks: RuleCheck[]; className?: string }) {
  const sorted = [...checks].sort((a, b) => Number(a.passed) - Number(b.passed))
  const failed = checks.filter((c) => !c.passed).length
  return (
    <div className={className}>
      <p className="mb-2 text-[12px] text-muted">
        <span className="num text-ink">{checks.length - failed}</span> passed ·{' '}
        <span className={cn('num', failed ? 'text-danger-text' : 'text-ink')}>{failed}</span> {failed === 1 ? 'violation' : 'violations'}
      </p>
      <ul className="divide-y divide-line rounded-[8px] border border-line">
        {sorted.map((c) => (
          <li key={c.rule_id} className={cn('flex items-start gap-2.5 px-3 py-2 text-[13px]', !c.passed && 'bg-danger-soft')}>
            <span
              aria-label={c.passed ? 'passed' : 'failed'}
              className={cn('num mt-px w-3 shrink-0 text-center font-semibold', c.passed ? 'text-ink' : 'text-danger-text')}
            >
              {c.passed ? '✓' : '✗'}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-ink">{c.description}</p>
              {c.detail ? <p className={cn('text-[12px]', c.passed ? 'text-muted' : 'text-danger-text')}>{c.detail}</p> : null}
            </div>
            <span className="num shrink-0 text-[11px] text-muted">{c.rule_id}</span>
            <SeverityTag severity={c.severity} />
          </li>
        ))}
      </ul>
    </div>
  )
}
