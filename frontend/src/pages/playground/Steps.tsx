import type { ReactNode } from 'react'
import { DecidedByBadge, StatusBadge } from '@/components/badges'
import { ExplanationCard } from '@/components/ExplanationCard'
import { Money } from '@/components/Money'
import { RuleCheckList } from '@/components/RuleCheckList'
import { TelegramPreview } from '@/components/TelegramPreview'
import { festivalLabel } from '@/lib/festivals'
import { PHASE_LABEL, POLICY_LABEL, TRIGGER_LABEL } from '@/lib/labels'
import type { Decision } from '@/lib/types'
import { cn, formatDateTime, formatInr, formatInt } from '@/lib/utils'

export type State = 'pass' | 'fail' | 'retry' | 'fallback' | 'skip' | 'info'
export interface Step {
  key: string
  title: string
  state: State
  summary: string
  body?: ReactNode
}

export const GLYPH: Record<State, string> = { pass: '✓', fail: '✗', retry: '↺', fallback: '◆', skip: '–', info: '•' }
export const RING: Record<State, string> = {
  pass: 'border-ink text-ink', fail: 'border-danger text-danger-text', retry: 'border-signal text-signal-text',
  fallback: 'border-violet text-violet-text', skip: 'border-dashed border-line text-muted', info: 'border-line text-muted',
}

/** Walks one dry-run decision through the harness, stage by stage, in plain English. */
export function buildSteps(d: Decision): Step[] {
  const blocked = d.decided_by === 'BLOCKED_PREGATE'
  const holdout = d.decided_by === 'HOLDOUT'
  const c = d.context
  const steps: Step[] = []

  steps.push({
    key: 'trigger', title: 'Trigger', state: 'info',
    summary: `${TRIGGER_LABEL[d.trigger]} for ${d.profile_snapshot.first_name} at ${formatDateTime(c.now)}${c.festival ? ` · ${festivalLabel(c.festival)} ${c.festival_phase ? PHASE_LABEL[c.festival_phase] : ''}` : ''}`,
    body: facts([
        ['Policy now', POLICY_LABEL[d.profile_snapshot.policy]],
        ['Churn risk', d.profile_snapshot.churn_risk.toFixed(2)],
        ['Quiet hours', c.is_quiet_hours ? 'yes' : 'no'],
        ['Budget left today', formatInr(c.budget_left_today)],
        ...(c.days_to_festival !== null ? [['Days to festival', String(c.days_to_festival)] as [string, string]] : []),
        ...(c.pacing_factor < 1 ? [['Pacing', `caps × ${c.pacing_factor.toFixed(2)}`] as [string, string]] : []),
    ]),
  })

  steps.push(blocked
    ? { key: 'pregate', title: 'Pre-gate', state: 'fail', summary: d.explanation.title.replace(/^Blocked:?\s*/, '') || 'Stopped before any offer was considered' }
    : holdout
      ? { key: 'pregate', title: 'Pre-gate', state: 'skip', summary: 'Customer is in the 10% holdout: nothing is sent, so we can measure what offers really add.' }
      : { key: 'pregate', title: 'Pre-gate', state: 'pass', summary: 'Consent, pause, kill switch, quiet hours and frequency all OK.' })

  if (!blocked && !holdout) {
    steps.push({
      key: 'policy', title: 'Effective policy', state: 'pass',
      summary: `${POLICY_LABEL[d.effective_policy.policy]} · ${formatInt(d.effective_policy.rules.length)} rules merged Global → Festival → Persona → Individual`,
      body: <ul className="space-y-0.5 text-[12.5px] text-muted">{d.effective_policy.summary.map((s) => <li key={s}>· {s}</li>)}</ul>,
    })
    steps.push({
      key: 'candidates', title: 'Allowed offers', state: d.candidates.length ? 'pass' : 'skip',
      summary: d.candidates.length ? `${d.candidates.length} offers survive the limits` : 'No offer is allowed for this customer right now',
      body: d.candidates.length ? (
        <ul className="divide-y divide-line rounded-[6px] border border-line text-[12.5px]">
          {d.candidates.map((o) => (
            <li key={o.offer_id} className="flex items-center justify-between gap-3 px-2.5 py-1.5">
              <span className={cn('num', o.offer_id === d.final_offer_id ? 'text-ink' : 'text-muted')}>
                {o.offer_id === d.final_offer_id ? '● ' : ''}{o.offer_id}
              </span>
              <span className="num shrink-0 text-muted">cost <Money value={o.est_cost} /> · profit <Money value={o.est_incremental_profit} /></span>
            </li>
          ))}
        </ul>
      ) : undefined,
    })

    const agentFailed = d.decided_by === 'RULES_FALLBACK'
    steps.push({
      key: 'agent', title: agentFailed ? 'AI agent → fallback' : 'AI agent',
      state: agentFailed ? 'fallback' : d.decided_by === 'AGENT_RETRY' ? 'retry' : 'pass',
      summary: agentFailed
        ? `Rules fallback decided: ${d.fallback_reason ?? 'the AI could not decide'}`
        : `${d.agent_trace.length} tool calls · ${formatInt(d.llm_tokens)} tokens · ${(d.latency_ms / 1000).toFixed(1)} s${d.decided_by === 'AGENT_RETRY' ? ' · retried once after a validation failure' : ''}`,
      body: d.agent_trace.length ? (
        <ol className="space-y-1 text-[12.5px]">
          {d.agent_trace.map((t, i) => (
            <li key={i} className="grid grid-cols-[1fr_auto] gap-2">
              <span><span className="num text-ink">{t.name}</span> <span className="text-muted">→ {t.result_summary}</span></span>
              <span className="num text-muted">{formatInt(t.ms)} ms</span>
            </li>
          ))}
        </ol>
      ) : undefined,
    })

    if (d.validation) {
      steps.push({
        key: 'validator', title: 'Final validator', state: d.validation.ok ? 'pass' : 'fail',
        summary: `rules.evaluate() re-checked the exact offer: ${d.validation.checks.length - d.validation.violations.length} passed · ${d.validation.violations.length} violations`,
        body: <RuleCheckList checks={d.validation.checks} />,
      })
    }
  }

  steps.push({
    key: 'result', title: 'Result', state: d.status === 'BLOCKED' ? 'fail' : d.status === 'SENT' || d.status === 'DRY_RUN' ? 'pass' : 'info',
    summary: d.explanation.title,
    body: (
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={d.status} />
          <DecidedByBadge by={d.decided_by} />
          {d.cost ? <span className="num text-[12px] text-muted">cost {formatInr(d.cost)} · expected profit {formatInr(d.expected_incremental_profit)}</span> : null}
        </div>
        <ExplanationCard explanation={d.explanation} decidedBy={d.decided_by} status={d.status} fallbackReason={d.fallback_reason} />
        {d.message ? <TelegramPreview d={d} /> : null}
      </div>
    ),
  })
  return steps
}

function facts(items: [string, string][]) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[12.5px] sm:grid-cols-3">
      {items.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-2 border-b border-line pb-0.5">
          <dt className="text-muted">{k}</dt>
          <dd className="num text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  )
}
