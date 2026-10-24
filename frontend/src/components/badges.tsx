import type { ReactNode } from 'react'
import { DECIDED_BY_LABEL, OUTCOME_LABEL, POLICY_LABEL, STATUS_LABEL } from '@/lib/labels'
import type { DecidedBy, DecisionStatus, Outcome, PolicyName } from '@/lib/types'
import { cn } from '@/lib/utils'

// Every badge carries a glyph or text, never colour alone.
type Tone = 'neutral' | 'signal' | 'violet' | 'amber' | 'danger' | 'ink'
const TONE: Record<Tone, string> = {
  neutral: 'border-line bg-surface-2 text-muted',
  ink: 'border-line bg-surface text-ink',
  signal: 'border-signal/40 bg-signal-soft text-signal-text',
  violet: 'border-violet/40 bg-violet-soft text-violet-text',
  amber: 'border-amber/50 bg-amber-soft text-amber-text',
  danger: 'border-danger/40 bg-danger-soft text-danger-text',
}

export function Badge({ tone = 'neutral', icon, children, className, title }: { tone?: Tone; icon?: ReactNode; children: ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cn('inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-[5px] border px-1.5 text-[11.5px] font-medium leading-none', TONE[tone], className)}
    >
      {icon ? <span aria-hidden className="text-[10px]">{icon}</span> : null}
      {children}
    </span>
  )
}

export function PolicyBadge({ policy }: { policy: PolicyName }) {
  return <Badge tone="ink">{POLICY_LABEL[policy]}</Badge>
}

const DECIDED: Record<DecidedBy, [Tone, string]> = {
  AGENT: ['signal', '●'],
  AGENT_RETRY: ['signal', '↺'],
  RULES_FALLBACK: ['violet', '◆'],
  BLOCKED_PREGATE: ['danger', '✗'],
  HOLDOUT: ['neutral', '◌'],
}
export function DecidedByBadge({ by }: { by: DecidedBy }) {
  const [tone, icon] = DECIDED[by]
  return <Badge tone={tone} icon={icon}>{DECIDED_BY_LABEL[by]}</Badge>
}

const STATUS: Record<DecisionStatus, [Tone, string]> = {
  SENT: ['ink', '✓'],
  QUEUED: ['amber', '⏱'],
  NO_OFFER: ['neutral', '—'],
  BLOCKED: ['danger', '✗'],
  HELD_OUT: ['neutral', '◌'],
  DRY_RUN: ['neutral', '▷'],
}
export function StatusBadge({ status }: { status: DecisionStatus }) {
  const [tone, icon] = STATUS[status]
  return <Badge tone={tone} icon={icon}>{STATUS_LABEL[status]}</Badge>
}

const OUTCOME: Record<Outcome, [Tone, string]> = {
  pending: ['neutral', '…'],
  claimed: ['ink', '✓'],
  redeemed: ['signal', '₹'],
  ignored: ['neutral', '—'],
  declined: ['danger', '✗'],
  remind_later: ['amber', '⏰'],
}
export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const [tone, icon] = OUTCOME[outcome]
  return <Badge tone={tone} icon={icon}>{OUTCOME_LABEL[outcome]}</Badge>
}

export function SeverityTag({ severity }: { severity: 'hard' | 'soft' }) {
  return (
    <span className="num rounded-[4px] border border-line px-1 text-[10.5px] uppercase tracking-wide text-muted">
      {severity}
    </span>
  )
}
