import type { ReactNode } from 'react'

/** One-line marketer note under every page title (T27). */
export function WhyThisPage({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-2 text-[13px] text-muted">
      <span className="num mt-px shrink-0 rounded-[4px] border border-line px-1 text-[10.5px] uppercase tracking-wide">Why</span>
      <span>{children}</span>
    </p>
  )
}
