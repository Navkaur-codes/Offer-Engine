import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Card, CardBody, CardHeader, CardTitle } from './ui/card'

/** Every chart leads with its one-sentence takeaway, so the point is readable without the chart. */
export function ChartCard({
  title, takeaway, legend, children, footnote, className,
}: { title: string; takeaway?: string | null; legend?: ReactNode; children: ReactNode; footnote?: ReactNode; className?: string }) {
  return (
    <Card className={cn('flex flex-col', className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {legend}
      </CardHeader>
      <CardBody className="flex flex-1 flex-col gap-3">
        {takeaway ? (
          <p className="text-[13.5px] leading-snug text-ink">
            <span aria-hidden className="mr-1.5 text-muted">→</span>
            {takeaway}
          </p>
        ) : (
          <p className="text-[12.5px] text-muted">Not enough data in this period for a takeaway.</p>
        )}
        <div className="min-h-0 flex-1">{children}</div>
        {footnote ? <p className="text-[11.5px] text-muted">{footnote}</p> : null}
      </CardBody>
    </Card>
  )
}

export function LegendKey({ items }: { items: [string, string][] }) {
  return (
    <ul className="flex flex-wrap items-center gap-3 text-[11.5px] text-muted">
      {items.map(([label, color]) => (
        <li key={label} className="flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-[2px]" style={{ background: color }} />
          {label}
        </li>
      ))}
    </ul>
  )
}
