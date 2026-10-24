import type { ReactNode } from 'react'
import type { DecidedBy, DecisionStatus, Explanation } from '@/lib/types'
import { DecidedByBadge, StatusBadge } from './badges'
import { PipelineLens } from './PipelineLens'
import { Card } from './ui/card'

/** The plain-English "why" for one decision (non-negotiable #7). */
export function ExplanationCard({
  explanation, decidedBy, status, fallbackReason,
}: {
  explanation: Explanation
  decidedBy: DecidedBy
  status: DecisionStatus
  fallbackReason?: string | null
}) {
  return (
    <Card>
      <div className="flex flex-col gap-3 border-b border-line p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={status} />
          <DecidedByBadge by={decidedBy} />
        </div>
        <h3 className="title text-[16px] text-ink">{explanation.title}</h3>
        <PipelineLens decision={{ decided_by: decidedBy, status, fallback_reason: fallbackReason, explanation_title: explanation.title }} />
      </div>
      <dl className="grid gap-3 p-4 text-[13px]">
        <Row term="Why this customer">{explanation.why_customer}</Row>
        <Row term="Why this offer">{explanation.why_offer}</Row>
        {explanation.rejected.length ? (
          <Row term="Alternatives rejected">
            <ul className="space-y-0.5">
              {explanation.rejected.map((r) => (
                <li key={r} className="flex gap-1.5">
                  <span aria-hidden className="text-muted">✗</span>
                  {r}
                </li>
              ))}
            </ul>
          </Row>
        ) : null}
        <Row term="Rules applied"><span className="num text-[12.5px]">{explanation.rules_line}</span></Row>
        <Row term="Decided by">{explanation.decided_by_line}</Row>
      </dl>
    </Card>
  )
}

function Row({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[150px_1fr] sm:gap-3">
      <dt className="text-[12px] font-medium text-muted">{term}</dt>
      <dd className="text-ink">{children}</dd>
    </div>
  )
}
