import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Always explains what is missing and offers one way forward. */
export function EmptyState({ title, hint, action, className }: { title: string; hint: string; action: ReactNode; className?: string }) {
  return (
    <div className={cn('dot-grid flex flex-col items-center justify-center gap-2 rounded-[8px] border border-dashed border-line px-6 py-12 text-center', className)}>
      <p className="title text-[14px] text-ink">{title}</p>
      <p className="max-w-sm text-[13px] text-muted">{hint}</p>
      <div className="mt-2">{action}</div>
    </div>
  )
}
