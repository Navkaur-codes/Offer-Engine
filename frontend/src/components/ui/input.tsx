import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return (
    <input
      className={cn(
        'h-8 w-full rounded-[6px] border border-line bg-surface px-2.5 text-[13px] text-ink placeholder:text-muted focus-visible:border-ink focus-visible:outline-none',
        className,
      )}
      {...props}
    />
  )
}
