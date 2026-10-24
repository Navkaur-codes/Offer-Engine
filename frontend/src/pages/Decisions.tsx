import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { DataTable } from '@/components/DataTable'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import { useDecisionParam } from '@/lib/decisionParam'
import { decisionColumns } from './decisionColumns'

export function Decisions() {
  const { open } = useDecisionParam()
  const list = useQuery({ queryKey: ['decisions', 'all'], queryFn: () => api.decisions({ limit: 100 }) })

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
        onRowClick={(d) => open(d.id)}
        empty={
          <EmptyState
            title="No decisions yet"
            hint="Decisions appear here as soon as a customer triggers one: try /simulate cart in the Telegram bot."
            action={<Button asChild><Link to="/playground">Run one in Playground</Link></Button>}
          />
        }
      />
    </div>
  )
}
