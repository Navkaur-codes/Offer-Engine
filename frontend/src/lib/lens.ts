// Derives Pipeline Lens chips (Pre-gate → Policy → Agent → Validator → Sent) from a decision.
import type { DecidedBy, DecisionStatus } from './types'

export type LensState = 'pass' | 'fail' | 'retry' | 'fallback' | 'skip' | 'wait'
export interface LensStep {
  key: 'pregate' | 'policy' | 'agent' | 'validator' | 'final'
  label: string
  state: LensState
  note: string
}

const FINAL_LABEL: Record<DecisionStatus, string> = {
  SENT: 'Sent', QUEUED: 'Queued', NO_OFFER: 'No offer', BLOCKED: 'Sent', HELD_OUT: 'Held out', DRY_RUN: 'Would send',
}

export function lensSteps(d: { decided_by: DecidedBy; status: DecisionStatus; fallback_reason?: string | null; explanation_title?: string }): LensStep[] {
  const blocked = d.decided_by === 'BLOCKED_PREGATE'
  const holdout = d.decided_by === 'HOLDOUT'
  const agent: LensStep = blocked || holdout
    ? { key: 'agent', label: 'Agent', state: 'skip', note: blocked ? 'Not called: stopped at pre-gate' : 'Not called: customer is in the 10% holdout' }
    : d.decided_by === 'RULES_FALLBACK'
      ? { key: 'agent', label: 'Fallback', state: 'fallback', note: `Rules fallback decided${d.fallback_reason ? `: ${d.fallback_reason}` : ''}` }
      : d.decided_by === 'AGENT_RETRY'
        ? { key: 'agent', label: 'Agent', state: 'retry', note: 'First proposal failed validation; agent retried once' }
        : { key: 'agent', label: 'Agent', state: 'pass', note: 'AI agent chose the offer inside the allowed limits' }

  const final: LensStep = { key: 'final', label: FINAL_LABEL[d.status], state: 'pass', note: 'Delivered on Telegram' }
  if (blocked) Object.assign(final, { state: 'skip', note: 'Nothing sent' })
  else if (d.status === 'QUEUED') Object.assign(final, { state: 'wait', note: 'Queued until quiet hours end (09:00 IST)' })
  else if (d.status === 'NO_OFFER') Object.assign(final, { state: 'skip', note: 'Decided not to send anything' })
  else if (d.status === 'HELD_OUT') Object.assign(final, { state: 'skip', note: 'Held out to measure incrementality' })
  else if (d.status === 'DRY_RUN') Object.assign(final, { note: 'Dry run: this offer would be sent; nothing was actually sent' })

  return [
    blocked
      ? { key: 'pregate', label: 'Pre-gate', state: 'fail', note: d.explanation_title?.replace(/^Blocked: /, '') ?? 'Blocked before any offer was considered' }
      : { key: 'pregate', label: 'Pre-gate', state: 'pass', note: 'Consent, quiet hours, kill switch and frequency all OK' },
    { key: 'policy', label: 'Policy', state: blocked ? 'skip' : 'pass', note: blocked ? 'Not reached' : 'Effective policy merged: Global → Festival → Persona → Individual' },
    agent,
    {
      key: 'validator', label: 'Validator', state: blocked || holdout || d.status === 'NO_OFFER' ? 'skip' : 'pass',
      note: blocked || holdout ? 'Not reached' : d.status === 'NO_OFFER' ? 'No offer to validate' : 'Final offer re-checked by rules.evaluate()',
    },
    final,
  ]
}
