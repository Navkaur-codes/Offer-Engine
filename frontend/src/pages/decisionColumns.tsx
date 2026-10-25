import { createColumnHelper } from '@tanstack/react-table'
import { DecidedByBadge, PolicyBadge, StatusBadge } from '@/components/badges'
import { Money } from '@/components/Money'
import { PipelineLens } from '@/components/PipelineLens'
import { festivalLabel } from '@/lib/festivals'
import { TRIGGER_LABEL } from '@/lib/labels'
import type { DecisionLight } from '@/lib/types'
import { formatDateTime } from '@/lib/utils'

const col = createColumnHelper<DecisionLight>()

export const decisionColumns = [
  col.accessor('ts', { header: 'Time', cell: (c) => <span className="num text-muted">{formatDateTime(c.getValue())}</span> }),
  col.accessor('first_name', {
    header: 'Customer',
    cell: (c) => (
      <span>
        {c.getValue()} <span className="num text-[11.5px] text-muted">{c.row.original.customer_id}</span>
      </span>
    ),
  }),
  col.accessor('policy', { header: 'Policy', cell: (c) => <PolicyBadge policy={c.getValue()} /> }),
  col.accessor('trigger', { header: 'Trigger', cell: (c) => <span className="text-muted">{TRIGGER_LABEL[c.getValue()]}</span> }),
  col.accessor('festival', {
    header: 'Festival',
    cell: (c) => (c.getValue() ? <span className="text-muted">{festivalLabel(c.getValue()!)}</span> : <span className="text-muted">—</span>),
  }),
  col.accessor('explanation_title', {
    header: 'Decision',
    enableSorting: false,
    cell: (c) => <span className="block max-w-[340px] truncate" title={c.getValue()}>{c.getValue()}</span>,
  }),
  col.display({ id: 'lens', header: 'Pipeline', cell: (c) => <PipelineLens decision={c.row.original} size="sm" className="flex-nowrap" /> }),
  col.accessor('status', { header: 'Status', cell: (c) => <StatusBadge status={c.getValue()} /> }),
  col.accessor('decided_by', { header: 'Decided by', cell: (c) => <DecidedByBadge by={c.getValue()} /> }),
  col.accessor('cost', { header: 'Cost', cell: (c) => <Money value={c.getValue()} className="text-muted" /> }),
]
