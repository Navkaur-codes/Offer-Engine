import type { ReactNode } from 'react'
import { WhyThisPage } from './WhyThisPage'

/** Title + one-line "why" + the page's single primary action. */
export function PageHeader({ title, why, action }: { title: string; why: string; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="space-y-1">
        <h1 className="title text-[22px] text-ink">{title}</h1>
        <WhyThisPage>{why}</WhyThisPage>
      </div>
      {action}
    </div>
  )
}
