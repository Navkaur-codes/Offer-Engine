import * as T from '@radix-ui/react-tooltip'
import type { ReactNode } from 'react'

export const TooltipProvider = T.Provider

export function Tip({ content, children, side = 'top' }: { content: ReactNode; children: ReactNode; side?: T.TooltipContentProps['side'] }) {
  return (
    <T.Root>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content
          side={side}
          sideOffset={6}
          className="z-50 max-w-72 rounded-[6px] bg-ink px-2.5 py-1.5 text-[12px] leading-snug text-bg shadow-menu"
        >
          {content}
        </T.Content>
      </T.Portal>
    </T.Root>
  )
}
