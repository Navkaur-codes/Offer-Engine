import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { History } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { SeverityTag } from '@/components/badges'
import { Money } from '@/components/Money'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Tip } from '@/components/ui/tooltip'
import { api } from '@/lib/api'
import { usePasscode } from '@/lib/hooks'
import { AFFIX, editableFields, segment, toParam, type EditField } from '@/lib/ruleEdit'
import type { Rule } from '@/lib/types'
import { cn, formatDateTime, formatInt } from '@/lib/utils'
import { VersionsDialog } from './VersionsDialog'

const TYPE_LABEL: Record<Rule['type'], string> = {
  margin_guard: 'Margin guard', discount_cap: 'Discount cap', frequency_cap: 'Frequency cap', quiet_hours: 'Quiet hours',
  budget: 'Budget', eligibility: 'Allowed offers', exclusion: 'Exclusion', stacking: 'Stacking',
  escalation_ladder: 'Escalation ladder', message: 'Message', festival_restriction: 'Festival restriction',
}

/** Debounce a value so the impact preview isn't requested on every keystroke. */
function useDebounced<T>(value: T, ms = 400): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export function RuleCard({ rule, highlight }: { rule: Rule; highlight?: boolean }) {
  const qc = useQueryClient()
  const { unlocked } = usePasscode()
  const fields = useMemo(() => editableFields(rule), [rule])
  const initial = useMemo(() => Object.fromEntries(fields.map((f) => [f.key, f.display])), [fields])
  const [draft, setDraft] = useState<Record<string, string>>(initial)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [seenVersion, setSeenVersion] = useState(rule.version)
  if (seenVersion !== rule.version) {
    // Saved or reverted elsewhere: drop the stale draft.
    setSeenVersion(rule.version)
    setDraft(initial)
  }

  const changed = fields.filter((f) => draft[f.key] !== f.display)
  const parsed = Object.fromEntries(changed.map((f) => [f.key, toParam(f, draft[f.key] ?? '')]))
  const invalid = changed.filter((f) => parsed[f.key] === null)
  const params = invalid.length ? null : parsed
  const debounced = useDebounced(params && changed.length ? params : null)

  const preview = useQuery({
    queryKey: ['rule-preview', rule.id, rule.version, debounced],
    queryFn: () => api.previewRule({ ...rule, params: { ...rule.params, ...debounced } }),
    enabled: Boolean(debounced),
  })

  const refresh = () => qc.invalidateQueries({ queryKey: ['rules'] })
  const undo = (from: number) => ({
    label: 'Undo',
    onClick: () => api.revertRule(rule.id, from).then(() => { toast(`Reverted to v${from}`); refresh() }),
  })
  const save = useMutation({
    mutationFn: () => api.updateRule(rule.id, { params: params ?? {} }),
    onSuccess: (r) => { toast(`Saved: now v${r.version}`, { description: r.description, action: undo(rule.version) }); refresh() },
  })
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api.updateRule(rule.id, { enabled }),
    onSuccess: (r) => { toast(`${r.enabled ? 'Turned on' : 'Turned off'}: ${r.id}`, { action: undo(rule.version) }); refresh() },
  })

  const { segments, extra } = segment(rule.description, fields)
  const lockedOff = rule.layer === 'global' && rule.severity === 'hard'

  return (
    <article
      id={`rule-${rule.id}`}
      className={cn(
        'rounded-[8px] border bg-surface p-4 transition-colors',
        highlight ? 'border-ink' : 'border-line',
        !rule.enabled && 'bg-surface-2',
      )}
    >
      <header className="mb-2 flex flex-wrap items-center gap-2 text-[12px] text-muted">
        <span className="num">{rule.id}</span>
        <span>·</span>
        <span>{TYPE_LABEL[rule.type]}</span>
        <SeverityTag severity={rule.severity} />
        <span className="num">v{rule.version}</span>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setHistoryOpen(true)} aria-label={`Version history for ${rule.id}`}>
            <History /> History
          </Button>
          <Switch
            checked={rule.enabled}
            label={`${rule.id} ${rule.enabled ? 'on' : 'off'}`}
            disabled={!unlocked || toggle.isPending || (lockedOff && rule.enabled)}
            title={lockedOff && rule.enabled ? 'Global hard limits can be tightened, not switched off' : !unlocked ? 'Unlock edits with the admin passcode' : undefined}
            onChange={(v) => toggle.mutate(v)}
          />
        </div>
      </header>

      <p className={cn('text-[14.5px] leading-8', rule.enabled ? 'text-ink' : 'text-muted line-through decoration-muted/40')}>
        {segments.map((s, i) =>
          'field' in s ? (
            <InlineField key={i} field={s.field} value={draft[s.field.key] ?? ''} invalid={invalid.includes(s.field)} onChange={(v) => setDraft({ ...draft, [s.field.key]: v })} />
          ) : (
            <span key={i}>{s.text}</span>
          ),
        )}
      </p>
      {extra.length ? (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-muted">
          {extra.map((f) => (
            <label key={f.key} className="flex items-center gap-1.5">
              {f.label}
              <InlineField field={f} value={draft[f.key] ?? ''} invalid={invalid.includes(f)} onChange={(v) => setDraft({ ...draft, [f.key]: v })} />
            </label>
          ))}
        </div>
      ) : null}

      {changed.length ? (
        <div className="mt-3 space-y-2 rounded-[6px] border border-line bg-bg p-3 text-[13px]">
          {invalid.length ? (
            <p className="text-danger-text">✗ {invalid.map((f) => f.label).join(', ')}: enter a number from 0{invalid.some((f) => f.unit === 'pct') ? ' to 100' : ''}.</p>
          ) : (
            <ImpactLine loading={preview.isFetching || !debounced} data={preview.data} />
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="primary" size="sm" disabled={!params || !unlocked || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? 'Saving…' : 'Save new version'}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDraft(initial)}>Cancel</Button>
            {!unlocked ? <span className="text-[12px] text-amber-text">⚠ Unlock edits with the admin passcode (top bar) to save.</span> : null}
          </div>
        </div>
      ) : null}

      <p className="num mt-2 text-[11px] text-muted">
        last change {formatDateTime(rule.updated_at)} by {rule.updated_by}
      </p>
      <VersionsDialog rule={rule} open={historyOpen} onOpenChange={setHistoryOpen} />
    </article>
  )
}

function InlineField({ field, value, invalid, onChange }: { field: EditField; value: string; invalid: boolean; onChange: (v: string) => void }) {
  const [pre, post] = AFFIX[field.unit]
  return (
    <span className="mx-0.5 inline-flex items-baseline whitespace-nowrap">
      {pre ? <span className="num text-muted">{pre}</span> : null}
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        inputMode={field.unit === 'time' ? 'text' : 'decimal'}
        aria-label={field.label}
        aria-invalid={invalid}
        size={Math.max(2, value.length + 1)}
        className={cn(
          'num h-7 rounded-[6px] border bg-surface px-1.5 text-center text-[14px] font-medium text-ink focus-visible:border-ink focus-visible:outline-none',
          invalid ? 'border-danger' : 'border-dashed border-muted/60 hover:border-ink',
        )}
      />
      {post ? <span className="num text-muted">{post}</span> : null}
    </span>
  )
}

function ImpactLine({ loading, data }: { loading: boolean; data?: { customers_affected: number; budget_delta: number; examples: unknown[] } }) {
  if (loading || !data) return <p className="text-muted">Estimating impact…</p>
  const ids = data.examples
    .map((e) => (typeof e === 'string' ? e : (e as { customer_id?: string })?.customer_id))
    .filter((x): x is string => Boolean(x))
    .slice(0, 3)
  return (
    <p className="text-ink">
      <b className="font-semibold">Impact preview:</b> affects <span className="num">{formatInt(data.customers_affected)}</span> customers ·
      budget <Money value={data.budget_delta} signed />
      {ids.length ? (
        <>
          {' '}· e.g.{' '}
          {ids.map((id, i) => (
            <span key={id}>
              {i ? ', ' : ''}
              <Tip content="Open this customer">
                <Link to={`/customers?id=${id}`} className="num underline-offset-2 hover:underline">{id}</Link>
              </Tip>
            </span>
          ))}
        </>
      ) : null}
    </p>
  )
}
