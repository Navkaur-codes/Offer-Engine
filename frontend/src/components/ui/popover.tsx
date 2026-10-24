import * as P from '@radix-ui/react-popover'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export const Popover = P.Root
export const PopoverTrigger = P.Trigger

export function PopoverContent({ className, align = 'end', sideOffset = 6, ...props }: ComponentProps<typeof P.Content>) {
  return (
    <P.Portal>
      <P.Content
        align={align}
        sideOffset={sideOffset}
        className={cn('z-50 w-72 rounded-[8px] border border-line bg-surface p-3 text-ink shadow-menu', className)}
        {...props}
      />
    </P.Portal>
  )
}
