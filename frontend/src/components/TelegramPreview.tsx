import type { Decision } from '@/lib/types'
import { formatDate, formatTime } from '@/lib/utils'

const BUTTONS = ['✅ Claim', '⏰ Remind me tonight', '🙅 Not for me', '❓ Why this?']

/** How the card looks in the customer's Telegram chat (CLAUDE.md §7 message format). */
export function TelegramPreview({ d }: { d: Decision }) {
  if (!d.message)
    return (
      <div className="rounded-[8px] border border-dashed border-line px-4 py-6 text-center text-[13px] text-muted">
        Nothing was sent to the customer, so there is no message to preview.
      </div>
    )
  const coupon = d.coupon_code
  const parts = coupon ? d.message.split(coupon) : [d.message]
  return (
    <div className="dot-grid rounded-[8px] border border-line bg-surface-2 p-4">
      <div className="max-w-[340px] overflow-hidden rounded-[12px] rounded-bl-[4px] border border-line bg-surface">
        <div className="space-y-1.5 px-3.5 pt-3 text-[13.5px] leading-snug text-ink">
          {d.headline ? <p className="font-semibold">{d.headline}</p> : null}
          <p>
            {parts.map((p, i) => (
              <span key={i}>
                {p}
                {i < parts.length - 1 ? <code className="num rounded-[4px] bg-surface-2 px-1 text-[12.5px]">{coupon}</code> : null}
              </span>
            ))}
          </p>
          <div className="flex items-center justify-between gap-2 pb-2.5 pt-1">
            {d.expires_at ? (
              <span className="num rounded-[4px] bg-amber-soft px-1.5 py-0.5 text-[11px] font-medium text-amber-text">
                expires {formatDate(d.expires_at)}
              </span>
            ) : <span />}
            <span className="num text-[11px] text-muted">{formatTime(d.ts)}</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-px border-t border-line bg-line">
          {BUTTONS.map((b) => (
            <span key={b} className="bg-surface py-1.5 text-center text-[12px] text-ink">{b}</span>
          ))}
        </div>
      </div>
      <p className="num mt-2 text-[11.5px] text-muted">
        {d.message.length}/280 chars · channel {d.channel}
      </p>
    </div>
  )
}
