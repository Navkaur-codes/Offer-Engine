import { Bar, BarChart, CartesianGrid, LabelList, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ReactNode } from 'react'
import { AXIS, GRID, LABEL } from '@/lib/chart'
import type { Benchmark, EventType, Festival, RealismStats } from '@/lib/types'
import { cn, formatDate, formatInr, formatInrCompact, formatInt } from '@/lib/utils'

function Tip({ children }: { children: ReactNode }) {
  return <div className="rounded-[6px] border border-line bg-surface px-2.5 py-1.5 text-[12px] text-ink shadow-menu">{children}</div>
}
const catLabel = (c: string) => c.replace('_', ' ').replace(/^./, (s) => s.toUpperCase())

/** The target band as a track, the actual value as a tick: in band = ✓, outside = ✗. */
export function BandMeter({ b, format }: { b: Benchmark; format: (v: number) => string }) {
  const lo = Math.min(b.min, b.value) * 0.8
  const hi = Math.max(b.max, b.value) * 1.15
  const at = (v: number) => ((v - lo) / (hi - lo)) * 100
  return (
    <div className="space-y-1">
      <div className="relative h-2.5 rounded-full bg-surface-2" aria-hidden>
        <div className="absolute inset-y-0 rounded-full bg-slate/35" style={{ left: `${at(b.min)}%`, width: `${at(b.max) - at(b.min)}%` }} />
        <div className={cn('absolute -top-1 h-[18px] w-[3px] rounded-full', b.ok ? 'bg-ink' : 'bg-danger')} style={{ left: `calc(${at(b.value)}% - 1.5px)` }} />
      </div>
      <p className="num text-[11px] text-muted">target {format(b.min)}–{format(b.max)}</p>
    </div>
  )
}

const FUNNEL: [EventType, string][] = [
  ['session', 'Visits'], ['view', 'Product views'], ['add_to_cart', 'Add to cart'], ['checkout_started', 'Checkout'], ['purchase', 'Purchases'],
]

export function FunnelBars({ funnel }: { funnel: RealismStats['funnel'] }) {
  const steps = FUNNEL.filter(([k]) => funnel[k] !== undefined).map(([k, label]) => ({ k, label, n: funnel[k] ?? 0 }))
  const max = Math.max(1, ...steps.map((s) => s.n))
  return (
    <ol className="space-y-2.5">
      {steps.map((s, i) => {
        const prev = i > 0 ? steps[i - 1].n : null
        return (
          <li key={s.k} className="space-y-1" title={`${s.label}: ${formatInt(s.n)}`}>
            <div className="flex items-baseline justify-between text-[12.5px]">
              <span className="text-ink">{s.label}</span>
              <span className="num">
                <span className="text-ink">{formatInt(s.n)}</span>
                {prev ? (
                  <span className="text-[11px] text-muted">
                    {' · '}
                    {s.n > prev ? `${(s.n / prev).toFixed(1)} per ${steps[i - 1].label.toLowerCase().replace(/s$/, '')}` : `${((s.n / prev) * 100).toFixed(1)}% of previous`}
                  </span>
                ) : null}
              </span>
            </div>
            <div className="h-3 rounded-[4px] bg-surface-2">
              <div className="h-full rounded-[4px] bg-slate" style={{ width: `${(s.n / max) * 100}%` }} />
            </div>
          </li>
        )
      })}
    </ol>
  )
}

/** Monthly cohorts × months since first order. One hue, darker = more customers still buying. */
export function CohortHeatmap({ rows }: { rows: RealismStats['retention_cohorts'] }) {
  const months = ['m1', 'm2', 'm3', 'm4', 'm5', 'm6']
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-[2px] text-[11.5px]">
        <thead>
          <tr className="text-muted">
            <th scope="col" className="px-1 text-left font-medium">First order</th>
            <th scope="col" className="px-1 text-right font-medium">Customers</th>
            {months.map((m) => <th key={m} scope="col" className="px-1 text-center font-medium">Month {m.slice(1)}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.cohort}>
              <th scope="row" className="num px-1 text-left font-normal text-ink">{r.cohort}</th>
              <td className="num px-1 text-right text-muted">{formatInt(r.size)}</td>
              {months.map((m) => {
                const v = typeof r[m] === 'number' ? (r[m] as number) : null
                return (
                  <td
                    key={m}
                    className="num h-7 rounded-[3px] text-center"
                    // Capped at 60% so dark ink stays readable on every cell (light and dark mode).
                    style={v === null ? undefined : { background: `color-mix(in oklab, var(--slate) ${Math.round(Math.min(1, v / 0.5) * 60)}%, var(--surface))`, color: 'var(--ink)' }}
                    title={v === null ? 'not yet' : `${(v * 100).toFixed(1)}% still buying in month ${m.slice(1)}`}
                  >
                    {v === null ? '' : `${Math.round(v * 100)}%`}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Daily revenue with a 7-day average; grey bands mark festival days from the calendar. */
export function SeasonalityLine({ rows, festivals }: { rows: RealismStats['seasonality_daily']; festivals: Festival[] }) {
  const data = rows.map((r, i) => {
    const win = rows.slice(Math.max(0, i - 6), i + 1)
    return { ...r, avg: Math.round(win.reduce((s, x) => s + x.revenue, 0) / win.length) }
  })
  const first = data[0]?.date ?? ''
  const last = data[data.length - 1]?.date ?? ''
  const marks = festivals.filter((f) => f.date >= first && f.date <= last && f.needs_opt_in)
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 16, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey="date" {...AXIS} minTickGap={48} tickFormatter={(d: string) => formatDate(d)} />
        <YAxis {...AXIS} width={52} tickFormatter={(v: number) => formatInrCompact(v)} />
        {marks.map((f) => (
          <ReferenceArea key={f.id} x1={f.date} x2={f.date} stroke="var(--line)" fill="var(--slate)" fillOpacity={0.15}
            label={{ value: f.name.split(/[/(]/)[0].trim(), position: 'top', fill: 'var(--muted)', fontSize: 10 }} />
        ))}
        <Tooltip
          content={({ payload }) => {
            const p = payload?.[0]?.payload as (typeof data)[number] | undefined
            return p ? <Tip>{formatDate(p.date)} · <span className="num">{formatInr(p.revenue)}</span><br /><span className="num text-muted">7-day avg {formatInr(p.avg)}</span></Tip> : null
          }}
        />
        <Line dataKey="revenue" stroke="var(--slate)" strokeOpacity={0.45} strokeWidth={1} dot={false} isAnimationActive={false} />
        <Line dataKey="avg" stroke="var(--signal)" strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function CategoryBars({ values, format, band }: { values: Record<string, number>; format: (v: number) => string; band?: { cat: string; min: number; max: number } }) {
  const data = Object.entries(values).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ k, name: catLabel(k), v }))
  return (
    <ResponsiveContainer width="100%" height={data.length * 26 + 20}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 64, left: 8, bottom: 0 }}>
        <XAxis type="number" hide domain={[0, 'dataMax']} />
        <YAxis type="category" dataKey="name" {...AXIS} tick={{ ...AXIS.tick, fontFamily: 'var(--font-sans)' }} width={92} axisLine={false} />
        {band ? <ReferenceArea x1={band.min} x2={band.max} fill="var(--slate)" fillOpacity={0.12} /> : null}
        <Tooltip cursor={{ fill: 'var(--surface-2)' }} content={({ payload }) => {
          const p = payload?.[0]?.payload as (typeof data)[number] | undefined
          return p ? <Tip>{p.name} · <span className="num">{format(p.v)}</span>{band && p.k === band.cat ? <><br /><span className="text-muted">target {format(band.min)}–{format(band.max)}</span></> : null}</Tip> : null
        }} />
        <Bar dataKey="v" barSize={12} radius={[0, 4, 4, 0]} fill="var(--slate)" isAnimationActive={false}>
          <LabelList dataKey="v" position="right" style={LABEL} formatter={(v: unknown) => format(Number(v))} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
