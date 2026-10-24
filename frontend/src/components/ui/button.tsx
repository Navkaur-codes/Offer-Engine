import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

// Signal rule: only `primary` uses the accent, and ideally once per view.
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[6px] text-[13px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-3.5 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary: 'bg-signal text-signal-fg hover:bg-signal/90',
        secondary: 'border border-line bg-surface text-ink hover:bg-surface-2',
        ghost: 'text-ink hover:bg-surface-2',
        danger: 'border border-danger/40 bg-danger-soft text-danger-text hover:border-danger',
        rail: 'border border-rail-line bg-transparent text-rail-ink hover:bg-white/5',
      },
      size: { sm: 'h-7 px-2.5', md: 'h-8 px-3', icon: 'size-8' },
    },
    defaultVariants: { variant: 'secondary', size: 'md' },
  },
)

export function Button({
  className, variant, size, asChild, ...props
}: ComponentProps<'button'> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'button'
  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />
}
