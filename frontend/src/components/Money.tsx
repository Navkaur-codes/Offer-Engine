import { cn, formatInr, formatInrCompact } from '@/lib/utils'

/** Always mono + tabular so ₹ columns line up. `signed` adds +/− for deltas. */
export function Money({ value, compact, signed, className }: { value: number; compact?: boolean; signed?: boolean; className?: string }) {
  const text = compact ? formatInrCompact(value) : formatInr(value)
  return <span className={cn('num', className)}>{signed && value > 0 ? `+${text}` : text}</span>
}
