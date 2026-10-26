import * as D from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { DecidedByBadge, PolicyBadge, StatusBadge } from '@/components/badges'
import { Money } from '@/components/Money'
import { useDecisionParam } from '@/lib/decisionParam'
import type { JobResult, PickRow } from '@/lib/types'
import { cn, formatInt, formatPct } from '@/lib/utils'

const category = (c: string | null) => (c ? c.replaceAll('_', ' ') : '—')

/** "Sent: 10% off fashion (exp. 02 Nov)" → "10% off fashion": the offer itself, for the mix chips. */
const offerOf = (r: PickRow) => r.title.replace(/^[^:]*:\s*/, '').replace(/\s*\(exp\.[^)]*\)$/, '')

/** The report after a personal-picks run: who got what, what it was based on, and why the rest got nothing. */
export function PicksReport({ result, onClose }: { result: JobResult | null; onClose: () => void }) {
  const { open: openDecision } = useDecisionParam()
  const rows = result?.rows ?? []
  const mix = new Map<string, number>()
  for (const r of rows) if (r.status === 'SENT' || r.status === 'QUEUED') mix.set(offerOf(r), (mix.get(offerOf(r)) ?? 0) + 1)
  const lab = rows.filter((r) => r.where === 'lab').length

  return (
    <D.Root open={!!result} onOpenChange={(v) => !v && onClose()}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <D.Content className="fixed inset-x-0 top-[4vh] z-50 mx-auto flex max-h-[92vh] w-[min(96vw,1040px)] flex-col overflow-hidden rounded-[8px] border border-line bg-bg text-ink shadow-menu focus:outline-none">
          <div className="flex items-start justify-between gap-3 border-b border-line bg-surface px-5 py-3">
            <div>
              <D.Title className="title text-[15px]">Personal picks: run report</D.Title>
              <D.Description className="text-[12.5px] text-muted">
                Each customer's pick is built on their own profile (top category, policy, predicted uplift) and passed the same rules as any offer.
                {lab ? ` The ${lab} Lab customers' picks are being posted in the Lab group now.` : ''}
              </D.Description>
            </div>
            <D.Close className="rounded-[6px] p-1.5 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Close"><X className="size-4" /></D.Close>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto p-5">
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <Tile term="Customers checked">{formatInt(result?.decisions ?? 0)}</Tile>
              <Tile term="Sent" strong>✓ {formatInt(result?.sent ?? 0)}</Tile>
              <Tile term="Queued for 09:00">{formatInt(result?.queued ?? 0)}</Tile>
              <Tile term="No offer · blocked">{formatInt(result?.no_offer ?? 0)} · ✗ {formatInt(result?.blocked ?? 0)}</Tile>
              <Tile term="Spent on offers"><Money value={result?.spent ?? 0} /></Tile>
            </dl>

            {mix.size ? (
              <div>
                <p className="mb-1.5 text-[12px] font-medium text-muted">Offer mix: different customers, different offers</p>
                <ul className="flex flex-wrap gap-1.5">
                  {[...mix.entries()].sort((a, b) => b[1] - a[1]).map(([offer, n]) => (
                    <li key={offer} className="rounded-[6px] border border-line bg-surface px-2 py-1 text-[12px]">
                      <span className="num text-ink">{n}×</span> {offer}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="overflow-x-auto rounded-[8px] border border-line bg-surface">
              <table className="w-full text-[12.5px]">
                <thead>
                  <tr className="border-b border-line text-left text-[11.5px] text-muted">
                    {['Customer', 'Where', 'Top category', 'Policy', 'Decision', 'Status', 'Decided by', 'Cost'].map((h) => <th key={h} className="h-8 px-3 font-medium">{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.decision_id} className="border-b border-line last:border-0 hover:bg-surface-2">
                      <td className="h-9 whitespace-nowrap px-3">
                        <button className="text-left hover:underline" onClick={() => openDecision(r.decision_id)}>
                          {r.first_name} <span className="num text-[11px] text-muted">{r.customer_id}</span>
                        </button>
                      </td>
                      <td className="whitespace-nowrap px-3 text-muted">{r.where === 'lab' ? 'Lab group' : 'Telegram DM'}</td>
                      <td className="whitespace-nowrap px-3 capitalize">
                        {category(r.category)}{r.category_share != null ? <span className="num text-muted"> · {formatPct(r.category_share, 0)}</span> : null}
                      </td>
                      <td className="px-3"><PolicyBadge policy={r.policy} /></td>
                      <td className="max-w-[300px] truncate px-3" title={r.title}>{r.title}</td>
                      <td className="px-3"><StatusBadge status={r.status} /></td>
                      <td className="px-3"><DecidedByBadge by={r.decided_by} /></td>
                      <td className="px-3"><Money value={r.cost} className="text-muted" /></td>
                    </tr>
                  ))}
                  {!rows.length ? (
                    <tr><td colSpan={8} className="px-3 py-6 text-center text-muted">No Telegram or Lab customers to pick for yet.</td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <p className="text-[11.5px] text-muted">
              Top category share = 60% of the customer's spend and 40% of their browsing. Click a name for the full decision and its reasons.
              Real Telegram customers aren't messaged 21:00–09:00; those picks wait for the morning.
            </p>
          </div>
        </D.Content>
      </D.Portal>
    </D.Root>
  )
}

function Tile({ term, children, strong }: { term: string; children: ReactNode; strong?: boolean }) {
  return (
    <div className="rounded-[8px] border border-line bg-surface px-3 py-2">
      <dt className="text-[11.5px] text-muted">{term}</dt>
      <dd className={cn('num mt-0.5 text-[16px] text-ink', strong && 'title')}>{children}</dd>
    </div>
  )
}
