import * as D from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export const Dialog = D.Root
export const DialogTrigger = D.Trigger
export const DialogClose = D.Close

export function DialogContent({
  className, children, title, description, ...props
}: ComponentProps<typeof D.Content> & { title: ReactNode; description?: ReactNode }) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-50 bg-black/40" />
      <D.Content
        className={cn(
          'fixed left-1/2 top-[18%] z-50 w-[min(92vw,440px)] -translate-x-1/2 rounded-[8px] border border-line bg-surface p-5 text-ink shadow-menu',
          className,
        )}
        {...props}
      >
        <D.Title className="title text-[15px]">{title}</D.Title>
        {description ? (
          <D.Description className="mt-1 text-[13px] text-muted">{description}</D.Description>
        ) : (
          <D.Description className="sr-only">{typeof title === 'string' ? title : 'Dialog'}</D.Description>
        )}
        <div className="mt-4">{children}</div>
        <D.Close className="absolute right-3 top-3 rounded-[6px] p-1 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Close">
          <X className="size-4" />
        </D.Close>
      </D.Content>
    </D.Portal>
  )
}
