import { useInfiniteQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { DataTable } from '@/components/DataTable'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import { useDecisionParam } from '@/lib/decisionParam'
import { festivalKey } from '@/lib/festivals'
import { useFestivals } from '@/lib/queries'
import { DECIDED_BY_LABEL, POLICY_LABEL, STATUS_LABEL, TRIGGER_LABEL } from '@/lib/labels'
import type { DecisionFilters } from '@/lib/types'
import { decisionColumns } from './decisionColumns'

const PAGE = 50
type FilterKey = 'status' | 'decided_by' | 'policy' | 'trigger' | 'festival' | 'q'
const KEYS: FilterKey[] = ['status', 'decided_by', 'policy', 'trigger', 'festival', 'q']

export function Decisions() {
  const [params, setParams] = useSearchParams()
  const { open } = useDecisionParam()
  const { data: festivals } = useFestivals()
  // One option per festival key ("diwali"), across years; the API matches any year.
  const festivalOptions = Object.fromEntries((festivals ?? []).map((f) => [festivalKey(f.id), f.name]))
  const FILTERS: { key: FilterKey; label: string; options: Record<string, string> }[] = [
    { key: 'status', label: 'Status', options: STATUS_LABEL },
    { key: 'decided_by', label: 'Decided by', options: DECIDED_BY_LABEL },
    { key: 'policy', label: 'Policy', options: POLICY_LABEL },
    { key: 'trigger', label: 'Trigger', options: TRIGGER_LABEL },
    { key: 'festival', label: 'Festival', options: festivalOptions },
  ]
  const filters = Object.fromEntries(KEYS.map((k) => [k, params.get(k) ?? undefined])) as Omit<DecisionFilters, 'limit' | 'cursor'>
  const active = KEYS.filter((k) => params.get(k))

  const setFilter = (key: FilterKey, value: string) =>
    setParams((p) => {
      if (value) p.set(key, value)
      else p.delete(key)
      return p
    }, { replace: true })

  const list = useInfiniteQuery({
    queryKey: ['decisions', 'log', filters],
    queryFn: ({ pageParam }) => api.decisions({ ...filters, limit: PAGE, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next ?? undefined,
  })
  const rows = list.data?.pages.flatMap((p) => p.items) ?? []

  return (
    <div className="mx-auto max-w-[1400px] space-y-4 p-4 md:p-6">
      <PageHeader
        title="Decisions"
        why={NAV[1].why}
        action={<Button variant="primary" asChild><Link to="/playground">Simulate a trigger</Link></Button>}
      />

      <div role="search" aria-label="Filter decisions" className="flex flex-wrap items-center gap-2">
        <SearchBox value={filters.q ?? ''} onChange={(v) => setFilter('q', v)} />
        {FILTERS.map((f) => (
          <label key={f.key} className="relative">
            <span className="sr-only">{f.label}</span>
            <select
              value={params.get(f.key) ?? ''}
              onChange={(e) => setFilter(f.key, e.target.value)}
              className={
                'h-8 appearance-none rounded-[6px] border bg-surface pl-2.5 pr-7 text-[13px] focus-visible:border-ink focus-visible:outline-none ' +
                (params.get(f.key) ? 'border-ink text-ink' : 'border-line text-muted')
              }
            >
              <option value="">{f.label}: all</option>
              {Object.entries(f.options).map(([value, label]) => (
                <option key={value} value={value}>{f.label}: {label}</option>
              ))}
            </select>
            <span aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-muted">▼</span>
          </label>
        ))}
        {active.length ? (
          <Button variant="ghost" size="sm" onClick={() => setParams((p) => { KEYS.forEach((k) => p.delete(k)); return p }, { replace: true })}>
            <X /> Clear {active.length} {active.length === 1 ? 'filter' : 'filters'}
          </Button>
        ) : null}
        <span className="num ml-auto text-[12px] text-muted" role="status">
          {list.isLoading ? 'loading…' : `${rows.length}${list.hasNextPage ? '+' : ''} decisions`}
        </span>
      </div>

      <DataTable
        columns={decisionColumns}
        data={rows}
        loading={list.isLoading}
        getRowId={(d) => d.id}
        onRowClick={(d) => open(d.id)}
        empty={
          active.length ? (
            <EmptyState
              title="No decisions match these filters"
              hint="Try removing a filter, or search by a customer name, customer ID or decision ID."
              action={<Button onClick={() => setParams((p) => { KEYS.forEach((k) => p.delete(k)); return p }, { replace: true })}>Clear filters</Button>}
            />
          ) : (
            <EmptyState
              title="No decisions yet"
              hint="Decisions appear here as soon as a customer triggers one: try /simulate cart in the Telegram bot."
              action={<Button asChild><Link to="/playground">Run one in Playground</Link></Button>}
            />
          )
        }
      />
      {list.hasNextPage ? (
        <div className="flex justify-center">
          <Button onClick={() => list.fetchNextPage()} disabled={list.isFetchingNextPage}>
            {list.isFetchingNextPage ? 'Loading…' : `Load ${PAGE} older decisions`}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

/** Debounced so typing doesn't fire a request per keystroke. */
function SearchBox({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [draft, setDraft] = useState(value)
  const [seen, setSeen] = useState(value)
  if (value !== seen) {
    // URL changed from outside (e.g. "Clear filters"): adopt it instead of re-applying the old draft.
    setSeen(value)
    setDraft(value)
  }
  useEffect(() => {
    if (draft === value) return
    const t = setTimeout(() => onChange(draft.trim()), 300)
    return () => clearTimeout(t)
  }, [draft, value, onChange])
  return (
    <Input
      type="search"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      placeholder="Search name, C000123 or decision ID"
      aria-label="Search decisions"
      className="w-64"
    />
  )
}
