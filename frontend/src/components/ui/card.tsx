import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export function Card({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('rounded-[8px] border border-line bg-surface', className)} {...props} />
}

export function CardHeader({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('flex items-center justify-between gap-3 border-b border-line px-4 py-2.5', className)} {...props} />
}

// h2: pages have one h1, so card titles are the next level (Lighthouse heading-order).
export function CardTitle({ className, ...props }: ComponentProps<'h2'>) {
  return <h2 className={cn('title text-[13px] text-ink', className)} {...props} />
}

export function CardBody({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('p-4', className)} {...props} />
}
