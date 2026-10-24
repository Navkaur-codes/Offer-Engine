// Plain-English labels for marketers. Enum values never appear raw in the UI.
import type { DecidedBy, DecisionStatus, FestivalPhase, Outcome, PolicyName, TriggerType } from './types'

export const POLICY_LABEL: Record<PolicyName, string> = {
  vip: 'VIP', deal_hunter: 'Deal hunter', at_risk: 'At risk', new_user: 'New user',
  cart_abandoner: 'Cart abandoner', window_shopper: 'Window shopper', high_returner: 'High returner',
  sleeping_dog: 'Sleeping dog', dormant: 'Dormant', default: 'Default',
}

export const TRIGGER_LABEL: Record<TriggerType, string> = {
  cart_abandoned: 'Cart abandoned', browse_interest: 'Browse interest', inactivity: 'Inactive',
  points_expiry: 'Points expiring', festival: 'Festival', payday: 'Payday', welcome: 'Welcome',
  campaign: 'Campaign', manual: 'Manual', lab: 'Customer Lab',
}

export const STATUS_LABEL: Record<DecisionStatus, string> = {
  SENT: 'Sent', QUEUED: 'Queued', NO_OFFER: 'No offer', BLOCKED: 'Blocked', HELD_OUT: 'Held out', DRY_RUN: 'Dry run',
}

export const DECIDED_BY_LABEL: Record<DecidedBy, string> = {
  AGENT: 'AI agent', AGENT_RETRY: 'AI agent · retry', RULES_FALLBACK: 'Rules fallback',
  BLOCKED_PREGATE: 'Pre-gate', HOLDOUT: 'Holdout',
}

export const OUTCOME_LABEL: Record<Outcome, string> = {
  pending: 'Pending', claimed: 'Claimed', redeemed: 'Redeemed', ignored: 'Ignored', declined: 'Declined', remind_later: 'Remind later',
}

export const PHASE_LABEL: Record<FestivalPhase, string> = {
  teaser: 'teaser', build_up: 'build-up', last_minute: 'last minute', post: 'post-festival',
}
