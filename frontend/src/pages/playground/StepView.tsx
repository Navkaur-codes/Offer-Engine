import { cn } from '@/lib/utils'
import { GLYPH, RING, type Step } from './Steps'

export function StepView({ step, index, last }: { step: Step; index: number; last: boolean }) {
  return (
    <li className="row-in relative grid grid-cols-[28px_1fr] gap-3">
      {!last ? <span aria-hidden className="absolute left-[13px] top-7 bottom-0 w-px bg-line" /> : null}
      <span
        aria-label={`${step.title}: ${step.state}`}
        className={cn('num z-[1] flex size-7 items-center justify-center rounded-full border-2 bg-bg text-[12px] font-semibold', RING[step.state])}
      >
        {GLYPH[step.state]}
      </span>
      <div className="min-w-0 pb-5">
        <p className="text-[11px] uppercase tracking-wide text-muted"><span className="num">{index + 1}</span> · {step.title}</p>
        <p className="mt-0.5 text-[13.5px] text-ink">{step.summary}</p>
        {step.body ? <div className="mt-2">{step.body}</div> : null}
      </div>
    </li>
  )
}
