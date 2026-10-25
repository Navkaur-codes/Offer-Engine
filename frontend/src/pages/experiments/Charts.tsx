import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { ReactNode } from 'react'
import { AXIS, GRID, LABEL } from '@/lib/chart'
import { POLICY_LABEL } from '@/lib/labels'
import { offerLabel } from '@/lib/takeaways'
import type { ArmStats, FestivalLift, OfferRoi, PolicyUplift, QiniPoint } from '@/lib/types'
import { cn, formatDate, formatInr, formatInrCompact, formatInt } from '@/lib/utils'

/** Bar value label that always sits right of the bar's right edge (the zero line for negative bars). */
function rightLabel(format: (v: number) => string) {
  return (p: { x?: unknown; y?: unknown; width?: unknown; height?: unknown; value?: unknown }) => {
    const x = Number(p.x), w = Number(p.width), y = Number(p.y), h = Number(p.height), v = Number(p.value)
    return (
      <text x={Math.max(x, x + w) + 6} y={y + h / 2} dominantBaseline="central" fill="var(--ink)" fontSize={11} fontFamily="var(--font-mono)">
        {format(v)}
      </text>
    )
  }
}

function Tip({ children }: { children: ReactNode }) {
  return <div className="rounded-[6px] border border-line bg-surface px-2.5 py-1.5 text-[12px] text-ink shadow-menu">{children}</div>
}

/** Treated vs holdout on two separate scales (small multiples, never a dual axis). */
export function ArmsBars({ t, c }: { t: ArmStats; c: ArmStats }) {
  const metrics: { label: string; tv: number; cv: number; fmt: (v: number) => string }[] = [
    { label: 'Bought within 7 days', tv: t.conv_rate, cv: c.conv_rate, fmt: (v) => `${(v * 100).toFixed(1)}%` },
    { label: 'Revenue per customer', tv: t.revenue_per_customer ?? (t.n ? t.revenue / t.n : 0), cv: c.revenue_per_customer ?? (c.n ? c.revenue / c.n : 0), fmt: formatInr },
  ]
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      {metrics.map((m) => {
        const max = Math.max(m.tv, m.cv, 1e-9)
        return (
          <div key={m.label} className="space-y-2">
            <p className="text-[12px] text-muted">{m.label}</p>
            {[
              ['Got offers', m.tv, 'bg-signal', `n = ${formatInt(t.n)}`],
              ['Holdout (no offers)', m.cv, 'bg-slate', `n = ${formatInt(c.n)}`],
            ].map(([label, v, cls, n]) => (
              <div key={label as string} className="space-y-1" title={`${label}: ${m.fmt(v as number)} (${n})`}>
                <div className="flex justify-between text-[12px]">
                  <span className="text-ink">{label as string} <span className="num text-[11px] text-muted">{n as string}</span></span>
                  <span className="num text-ink">{m.fmt(v as number)}</span>
                </div>
                <div className="h-3 rounded-[4px] bg-surface-2">
                  <div className={cn('h-full rounded-[4px]', cls as string)} style={{ width: `${((v as number) / max) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

export function PolicyUpliftChart({ rows }: { rows: PolicyUplift[] }) {
  const data = [...rows].sort((a, b) => b.uplift - a.uplift).map((r) => ({ ...r, name: POLICY_LABEL[r.policy] ?? r.policy, pts: +(r.uplift * 100).toFixed(1) }))
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, data.length * 30 + 30)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, left: 8, bottom: 4 }}>
        <CartesianGrid {...GRID} horizontal={false} vertical />
        <XAxis type="number" {...AXIS} tickFormatter={(v: number) => `${v} pts`} />
        <YAxis type="category" dataKey="name" {...AXIS} tick={{ ...AXIS.tick, fontFamily: 'var(--font-sans)' }} width={112} />
        <ReferenceLine x={0} stroke="var(--muted)" />
        <Tooltip
          cursor={{ fill: 'var(--surface-2)' }}
          content={({ payload }) => {
            const r = payload?.[0]?.payload as (typeof data)[number] | undefined
            return r ? (
              <Tip>
                <b className="font-medium">{r.name}</b>: {r.uplift >= 0 ? '+' : ''}{r.pts} pts
                <br />
                <span className="num text-muted">treated {(r.treated_conv * 100).toFixed(1)}% (n {r.n_treated}) · holdout {(r.control_conv * 100).toFixed(1)}% (n {r.n_control})</span>
              </Tip>
            ) : null
          }}
        />
        <Bar dataKey="pts" radius={[0, 4, 4, 0]} barSize={14} isAnimationActive={false}>
          {data.map((d) => <Cell key={d.policy} fill={d.uplift < 0 ? 'var(--danger)' : 'var(--slate)'} />)}
          <LabelList dataKey="pts" content={rightLabel((v) => (v < 0 ? `▼ −${Math.abs(v)}` : `+${v}`))} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function RoiChart({ rows }: { rows: OfferRoi[] }) {
  const data = [...rows].sort((a, b) => b.incremental_profit - a.incremental_profit).map((r) => ({ ...r, name: offerLabel(r.type) }))
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 34 + 30)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 72, left: 8, bottom: 4 }}>
        <CartesianGrid {...GRID} horizontal={false} vertical />
        <XAxis type="number" {...AXIS} tickFormatter={(v: number) => formatInrCompact(v)} />
        <YAxis type="category" dataKey="name" {...AXIS} tick={{ ...AXIS.tick, fontFamily: 'var(--font-sans)' }} width={112} />
        <ReferenceLine x={0} stroke="var(--muted)" />
        <Tooltip
          cursor={{ fill: 'var(--surface-2)' }}
          content={({ payload }) => {
            const r = payload?.[0]?.payload as (typeof data)[number] | undefined
            return r ? (
              <Tip>
                <b className="font-medium">{r.name}</b> · {formatInt(r.n)} offers
                <br />
                <span className="num text-muted">extra profit {formatInr(r.incremental_profit)} · cost {formatInr(r.cost)} · extra revenue {formatInr(r.incremental_revenue)}</span>
              </Tip>
            ) : null
          }}
        />
        <Bar dataKey="incremental_profit" radius={[0, 4, 4, 0]} barSize={14} isAnimationActive={false}>
          {data.map((d) => <Cell key={d.type} fill={d.incremental_profit < 0 ? 'var(--danger)' : 'var(--slate)'} />)}
          <LabelList dataKey="incremental_profit" content={rightLabel((v) => `${v < 0 ? '▼ ' : ''}${formatInrCompact(v)}`)} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function QiniChart({ points }: { points: QiniPoint[] }) {
  const data = points.map((p) => ({ ...p, pct: Math.round(p.targeted * 100) }))
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 16 }}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey="pct" {...AXIS} tickFormatter={(v: number) => `${v}%`}
          label={{ value: 'share of customers targeted →', position: 'insideBottom', offset: -8, fill: 'var(--muted)', fontSize: 11 }} />
        <YAxis {...AXIS} width={52} tickFormatter={(v: number) => v.toFixed(3)} />
        <Tooltip
          content={({ payload }) => {
            const p = payload?.[0]?.payload as (typeof data)[number] | undefined
            return p ? (
              <Tip>
                Top <span className="num">{p.pct}%</span> targeted
                <br />
                <span className="num">model {p.model.toFixed(4)} · random {p.random.toFixed(4)}</span>
              </Tip>
            ) : null
          }}
        />
        <Line dataKey="model" name="By uplift model" stroke="var(--signal)" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line dataKey="random" name="Random" stroke="var(--slate)" strokeWidth={2} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function FestivalLiftChart({ rows }: { rows: FestivalLift[] }) {
  const data = rows.filter((r) => r.revenue_per_day > 0).sort((a, b) => a.date.localeCompare(b.date)).map((r) => ({ ...r, short: r.festival.split(/[/(]/)[0].trim() }))
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 20, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey="short" {...AXIS} tick={{ ...AXIS.tick, fontFamily: 'var(--font-sans)' }} interval={0} />
        <YAxis {...AXIS} width={36} tickFormatter={(v: number) => `${v}×`} />
        <ReferenceLine y={1} stroke="var(--muted)" strokeDasharray="4 4" label={{ value: 'normal day', position: 'insideTopRight', fill: 'var(--muted)', fontSize: 11 }} />
        <Tooltip
          cursor={{ fill: 'var(--surface-2)' }}
          content={({ payload }) => {
            const r = payload?.[0]?.payload as (typeof data)[number] | undefined
            return r ? (
              <Tip>
                <b className="font-medium">{r.festival}</b> · {formatDate(r.date)}
                <br />
                <span className="num text-muted">{formatInr(r.revenue_per_day)}/day vs {formatInr(r.baseline_per_day)} baseline</span>
              </Tip>
            ) : null
          }}
        />
        <Bar dataKey="lift" fill="var(--slate)" radius={[4, 4, 0, 0]} barSize={22} isAnimationActive={false}>
          <LabelList dataKey="lift" position="top" style={LABEL} formatter={(v: unknown) => `${Number(v).toFixed(1)}×`} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
