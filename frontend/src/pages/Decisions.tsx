import * as D from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { DataTable } from '@/components/DataTable'
import { EmptyState } from '@/components/EmptyState'
import { ExplanationCard } from '@/components/ExplanationCard'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { RuleCheckList } from '@/components/RuleCheckList'
import { Button } from '@/components/ui/button'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import { decisionColumns } from './decisionColumns'

// Phase-1 version: table + detail drawer. Filters, Telegram preview and trace timeline come in Phase 2.
export function Decisions() {
  const [params, setParams] = useSearchParams()
  const openId = params.get('id')
  const list = useQuery({ queryKey: ['decisions', 'all'], queryFn: () => api.decisions({ limit: 100 }) })

  const close = () => {
    params.delete('id')
    setParams(params, { replace: true })
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 md:p-6">
      <PageHeader
        title="Decisions"
        why={NAV[1].why}
        action={<Button variant="primary" asChild><Link to="/playground">Simulate a trigger</Link></Button>}
      />
      <DataTable
        columns={decisionColumns}
        data={list.data?.items ?? []}
        loading={list.isLoading}
        getRowId={(d) => d.id}
        onRowClick={(d) => setParams({ id: d.id })}
        empty={
          <EmptyState
            title="No decisions yet"
            hint="Decisions appear here as soon as a customer triggers one: try /simulate cart in the Telegram bot."
            action={<Button asChild><Link to="/playground">Run one in Playground</Link></Button>}
          />
        }
      />
      <D.Root open={Boolean(openId)} onOpenChange={(v) => !v && close()}>
        <D.Portal>
          <D.Overlay className="fixed inset-0 z-40 bg-black/30" />
          <D.Content className="fixed inset-y-0 right-0 z-50 flex w-[min(100vw,560px)] flex-col border-l border-line bg-bg shadow-menu">
            <div className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-surface px-4">
              <D.Title className="num text-[13px] text-ink">{openId}</D.Title>
              <D.Description className="sr-only">Decision detail with explanation and rule checks</D.Description>
              <D.Close className="rounded-[6px] p-1 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Close">
                <X className="size-4" />
              </D.Close>
            </div>
            {openId ? <DecisionDetail id={openId} /> : null}
          </D.Content>
        </D.Portal>
      </D.Root>
    </div>
  )
}

function DecisionDetail({ id }: { id: string }) {
  const { data: d, isLoading, isError } = useQuery({ queryKey: ['decision', id], queryFn: () => api.decision(id), retry: false })
  if (isLoading) return <div className="m-4 h-64 animate-pulse rounded-[8px] bg-surface-2" />
  if (isError || !d)
    return (
      <EmptyState className="m-4" title="Decision not found" hint={`No decision with ID ${id}. Check the ID or pick one from the table.`} action={<D.Close asChild><Button>Back to the list</Button></D.Close>} />
    )
  return (
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      <ExplanationCard explanation={d.explanation} decidedBy={d.decided_by} status={d.status} fallbackReason={d.fallback_reason} />
      <dl className="grid grid-cols-3 gap-3 text-[13px]">
        <Stat term="Cost"><Money value={d.cost} /></Stat>
        <Stat term="Expected incr. profit"><Money value={d.expected_incremental_profit} /></Stat>
        <Stat term="Coupon"><span className="num">{d.coupon_code ?? '—'}</span></Stat>
      </dl>
      {d.validation ? <RuleCheckList checks={d.validation.checks} /> : null}
    </div>
  )
}

function Stat({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="rounded-[8px] border border-line bg-surface p-3">
      <dt className="text-[11.5px] text-muted">{term}</dt>
      <dd className="mt-1 text-[15px] text-ink">{children}</dd>
    </div>
  )
}
