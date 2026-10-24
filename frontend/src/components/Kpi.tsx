import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * `hero` paints the number in signal orange. Use it on at most one KPI per page.
 * `delta` is a fraction vs yesterday; `goodWhen` decides whether ▲ reads as good.
 */
export function Kpi({
  label, value, delta, goodWhen = 'up', spark, hero, hint, className,
}: {
  label: string
  value: ReactNode
  delta?: number
  goodWhen?: 'up' | 'down'
  spark?: number[]
  hero?: boolean
  hint?: string
  className?: string
}) {
  return (
    <div className={cn('flex flex-col gap-2 rounded-[8px] border border-line bg-surface p-4', className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium text-muted">{label}</span>
        {delta !== undefined ? <Delta value={delta} goodWhen={goodWhen} /> : null}
      </div>
      <div className={cn('num title leading-none', hero ? 'text-[40px] text-signal' : 'text-[28px] text-ink')}>{value}</div>
      <div className="flex min-h-6 items-end justify-between gap-3">
        {hint ? <span className="text-[12px] text-muted">{hint}</span> : <span />}
        {spark && spark.length > 1 ? <Sparkline data={spark} hero={hero} /> : null}
      </div>
    </div>
  )
}

export function Delta({ value, goodWhen = 'up' }: { value: number; goodWhen?: 'up' | 'down' }) {
  const up = value >= 0
  const good = up === (goodWhen === 'up')
  return (
    <span
      className={cn('num inline-flex items-center gap-0.5 text-[12px]', good ? 'text-ink' : 'text-danger-text')}
      aria-label={`${up ? 'up' : 'down'} ${Math.abs(value * 100).toFixed(1)}% vs yesterday`}
    >
      <span aria-hidden>{up ? '▲' : '▼'}</span>
      {Math.abs(value * 100).toFixed(1)}%
    </span>
  )
}

export function Sparkline({ data, hero, width = 88, height = 24 }: { data: number[]; hero?: boolean; width?: number; height?: number }) {
  const min = Math.min(...data)
  const span = Math.max(...data) - min || 1
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - 2 - ((v - min) / span) * (height - 4)}`).join(' ')
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden className="shrink-0">
      <polyline points={pts} fill="none" stroke={hero ? 'var(--signal)' : 'var(--muted)'} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}
