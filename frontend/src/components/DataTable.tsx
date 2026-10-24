import {
  flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef, type SortingState,
} from '@tanstack/react-table'
import { useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Dense TanStack table with a sticky header. Rows are keyboard-activatable when `onRowClick` is set. */
export function DataTable<T>({
  columns, data, onRowClick, getRowId, loading, empty, maxHeight = '70vh', className,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<T, any>[]
  data: T[]
  onRowClick?: (row: T) => void
  getRowId?: (row: T) => string
  loading?: boolean
  empty?: ReactNode
  maxHeight?: string
  className?: string
}) {
  const [sorting, setSorting] = useState<SortingState>([])
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data, columns, state: { sorting }, onSortingChange: setSorting, getRowId,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(),
  })
  const rows = table.getRowModel().rows

  if (!loading && rows.length === 0 && empty) return <>{empty}</>

  return (
    <div className={cn('overflow-auto rounded-[8px] border border-line bg-surface', className)} style={{ maxHeight }}>
      <table className="w-full border-collapse text-[13px]">
        <thead className="sticky top-0 z-10 bg-surface">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const sorted = h.column.getIsSorted()
                return (
                  <th
                    key={h.id}
                    scope="col"
                    aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : undefined}
                    className="h-8 whitespace-nowrap border-b border-line px-3 text-left text-[11.5px] font-medium text-muted"
                  >
                    {h.isPlaceholder ? null : h.column.getCanSort() ? (
                      <button className="inline-flex items-center gap-1 hover:text-ink" onClick={h.column.getToggleSortingHandler()}>
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        <span aria-hidden className="num text-[10px]">{sorted === 'asc' ? '▲' : sorted === 'desc' ? '▼' : ''}</span>
                      </button>
                    ) : (
                      flexRender(h.column.columnDef.header, h.getContext())
                    )}
                  </th>
                )
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 6 }, (_, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  {columns.map((_c, j) => (
                    <td key={j} className="h-9 px-3">
                      <div className="h-3 w-3/4 animate-pulse rounded bg-surface-2" />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  onKeyDown={onRowClick ? (e) => e.key === 'Enter' && onRowClick(row.original) : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  className={cn('border-b border-line last:border-0', onRowClick && 'cursor-pointer hover:bg-surface-2 focus-visible:bg-surface-2')}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="h-9 whitespace-nowrap px-3 align-middle">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}
