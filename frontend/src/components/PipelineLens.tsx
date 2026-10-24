import { Fragment } from 'react'
import { lensSteps, type LensState, type LensStep } from '@/lib/lens'
import type { DecidedBy, DecisionStatus } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Tip } from './ui/tooltip'

const GLYPH: Record<LensState, string> = { pass: '✓', fail: '✗', retry: '↺', fallback: '◆', skip: '–', wait: '⏱' }
const STATE_TEXT: Record<LensState, string> = {
  pass: 'passed', fail: 'failed', retry: 'retried', fallback: 'rules fallback', skip: 'skipped', wait: 'waiting',
}

function chipClass(step: LensStep) {
  if (step.state === 'fail') return 'border-danger/50 bg-danger-soft text-danger-text'
  if (step.state === 'fallback') return 'border-violet/50 bg-violet-soft text-violet-text'
  if (step.state === 'wait') return 'border-amber/60 bg-amber-soft text-amber-text'
  if (step.state === 'skip') return 'border-dashed border-line text-muted'
  if (step.key === 'agent') return 'border-signal/50 bg-signal-soft text-signal-text'
  return 'border-line bg-surface text-ink'
}

/** The signature element: every decision's walk through the guardrails. */
export function PipelineLens({
  decision, size = 'md', className,
}: {
  decision: { decided_by: DecidedBy; status: DecisionStatus; fallback_reason?: string | null; explanation_title?: string }
  size?: 'sm' | 'md'
  className?: string
}) {
  const steps = lensSteps(decision)
  return (
    <ol className={cn('flex flex-wrap items-center gap-1', className)} aria-label="Decision pipeline">
      {steps.map((s, i) => (
        <Fragment key={s.key}>
          {i > 0 ? <li aria-hidden className="text-[11px] text-muted">→</li> : null}
          <li>
            <Tip content={<><b className="font-semibold">{s.label}: {STATE_TEXT[s.state]}.</b> {s.note}</>}>
              <span
                tabIndex={0}
                aria-label={`${s.label} ${STATE_TEXT[s.state]}. ${s.note}`}
                className={cn(
                  'inline-flex items-center gap-1 rounded-[5px] border font-medium',
                  size === 'sm' ? 'h-5 px-1.5 text-[11px]' : 'h-6 px-2 text-[12px]',
                  chipClass(s),
                )}
              >
                <span aria-hidden className="num">{GLYPH[s.state]}</span>
                {s.label}
              </span>
            </Tip>
          </li>
        </Fragment>
      ))}
    </ol>
  )
}
