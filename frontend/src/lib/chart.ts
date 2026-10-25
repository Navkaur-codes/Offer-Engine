// Shared Recharts styling so every chart uses the Signal tokens (recessive grid, mono numbers).
export const AXIS = {
  stroke: 'var(--line)',
  tick: { fill: 'var(--muted)', fontSize: 11, fontFamily: 'var(--font-mono)' },
  tickLine: false,
  axisLine: { stroke: 'var(--line)' },
} as const

export const GRID = { stroke: 'var(--line)', vertical: false } as const

export const LABEL = { fill: 'var(--ink)', fontSize: 11, fontFamily: 'var(--font-mono)' } as const

/** Chart order from CLAUDE.md §7: signal, violet, slate, amber. */
export const SERIES = ['var(--signal)', 'var(--violet)', 'var(--slate)', 'var(--amber)'] as const
