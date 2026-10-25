import { keepPreviousData, useInfiniteQuery } from '@tanstack/react-query'
import { createColumnHelper } from '@tanstack/react-table'
import { Megaphone, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PolicyBadge } from '@/components/badges'
import { CampaignDialog } from '@/components/CampaignDialog'
import { DataTable } from '@/components/DataTable'
import { EmptyState } from '@/components/EmptyState'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import { POLICY_LABEL } from '@/lib/labels'
import type { CustomerProfile, PolicyName } from '@/lib/types'
import { cn } from '@/lib/utils'
import { CustomerDrawer } from './customers/CustomerDrawer'
import { PolicyGlyph, SegmentScatter } from './customers/Scatter'

// The API builds each profile live (~55 ms on Neon), so 50 keeps the first paint near 3 s.
const PAGE = 50
const col = createColumnHelper<CustomerProfile>()

const columns = [
  col.accessor('first_name', {
    header: 'Customer',
    cell: (c) => <span>{c.getValue()} <span className="num text-[11.5px] text-muted">{c.row.original.customer_id}</span></span>,
  }),
  col.accessor('policy', {
    header: 'Policy',
    cell: (c) => <span className="inline-flex items-center gap-1.5"><PolicyGlyph policy={c.getValue()} /><PolicyBadge policy={c.getValue()} /></span>,
  }),
  col.accessor('tier', { header: 'Tier', cell: (c) => <span className="text-muted">{c.getValue()}</span> }),
  col.accessor('recency_days', { header: 'Last visit', cell: (c) => <span className="num">{c.getValue()} d ago</span> }),
  col.accessor('orders_90d', { header: 'Orders 90 d', cell: (c) => <span className="num">{c.getValue()}</span> }),
  col.accessor('aov', { header: 'Avg order', cell: (c) => <Money value={c.getValue()} /> }),
  col.accessor('ltv', { header: 'Lifetime value', cell: (c) => <Money value={c.getValue()} /> }),
  col.accessor('churn_risk', {
    header: 'Churn risk',
    cell: (c) => {
      const v = c.getValue()
      return <span className={cn('num', v >= 0.6 && 'text-danger-text')}>{v >= 0.6 ? '▲ ' : ''}{v.toFixed(2)}</span>
    },
  }),
  col.accessor('open_cart', {
    header: 'Open cart',
    enableSorting: false,
    cell: (c) => (c.getValue() ? <Money value={c.getValue()!.value} className="text-muted" /> : <span className="text-muted">—</span>),
  }),
]

export function Customers() {
  const [params, setParams] = useSearchParams()
  const policy = (params.get('policy') as PolicyName | null) ?? undefined
  const q = params.get('q') ?? ''
  const openId = params.get('id')

  const set = (key: string, value: string | null) =>
    setParams((p) => {
      if (value) p.set(key, value)
      else p.delete(key)
      return p
    }, { replace: key !== 'id' })

  const list = useInfiniteQuery({
    queryKey: ['customers', 'list', policy, q],
    queryFn: ({ pageParam }) => api.customers({ policy, q: q || undefined, limit: PAGE, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next ?? undefined,
    placeholderData: keepPreviousData,
  })
  const rows = list.data?.pages.flatMap((p) => p.items) ?? []

  return (
    <div className="mx-auto max-w-[1400px] space-y-4 p-4 md:p-6">
      <PageHeader
        title="Customers"
        why={NAV[3].why}
        action={<Button variant="primary" onClick={() => set('dryrun', '1')}><Megaphone /> Campaign dry-run</Button>}
      />

      <div role="search" aria-label="Filter customers" className="flex flex-wrap items-center gap-2">
        <SearchBox value={q} onChange={(v) => set('q', v)} />
        <label className="relative">
          <span className="sr-only">Policy</span>
          <select
            value={policy ?? ''}
            onChange={(e) => set('policy', e.target.value)}
            className={cn(
              'h-8 appearance-none rounded-[6px] border bg-surface pl-2.5 pr-7 text-[13px] focus-visible:border-ink focus-visible:outline-none',
              policy ? 'border-ink text-ink' : 'border-line text-muted',
            )}
          >
            <option value="">Policy: all</option>
            {Object.entries(POLICY_LABEL).map(([v, l]) => <option key={v} value={v}>Policy: {l}</option>)}
          </select>
          <span aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-muted">▼</span>
        </label>
        {policy || q ? (
          <Button variant="ghost" size="sm" onClick={() => setParams({}, { replace: true })}>
            <X /> Clear filters
          </Button>
        ) : null}
        <span className="num ml-auto text-[12px] text-muted" role="status">
          {list.isLoading ? 'loading…' : `${rows.length}${list.hasNextPage ? '+' : ''} customers`}
        </span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Segments: recency × value</CardTitle>
          <span className="text-[11.5px] text-muted">
            {rows.length} loaded customers · top-left = recent, high value · click a point to open
          </span>
        </CardHeader>
        <CardBody>
          {rows.length ? (
            <SegmentScatter
              customers={rows}
              selected={openId}
              activePolicy={policy}
              onSelect={(id) => set('id', id)}
              onTogglePolicy={(p) => set('policy', policy === p ? null : p)}
            />
          ) : list.isLoading ? (
            <div className="h-[300px] animate-pulse rounded-[6px] bg-surface-2" />
          ) : null}
        </CardBody>
      </Card>

      <DataTable
        columns={columns}
        data={rows}
        loading={list.isLoading}
        getRowId={(c) => c.customer_id}
        onRowClick={(c) => set('id', c.customer_id)}
        maxHeight="60vh"
        empty={
          <EmptyState
            title="No customers match"
            hint="Try another name or ID, or clear the policy filter. Real Telegram users have IDs starting with TG."
            action={<Button onClick={() => setParams({}, { replace: true })}>Clear filters</Button>}
          />
        }
      />
      {list.hasNextPage ? (
        <div className="flex justify-center">
          <Button onClick={() => list.fetchNextPage()} disabled={list.isFetchingNextPage}>
            {list.isFetchingNextPage ? 'Loading…' : `Load ${PAGE} more`}
          </Button>
        </div>
      ) : null}

      <CustomerDrawer id={openId} onClose={() => set('id', null)} />
      <CampaignDialog open={params.get('dryrun') === '1'} onOpenChange={(v) => set('dryrun', v ? '1' : null)} />
    </div>
  )
}

function SearchBox({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [draft, setDraft] = useState(value)
  const [seen, setSeen] = useState(value)
  if (value !== seen) {
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
      placeholder="Search name or ID (C000123, TG…)"
      aria-label="Search customers"
      className="w-64"
    />
  )
}
