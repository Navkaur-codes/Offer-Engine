import { NavLink } from 'react-router-dom'
import { USE_MOCKS } from '@/lib/api'
import { useHealth, useKillswitch } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { NAV } from './nav'

export function Wordmark() {
  return (
    <div className="flex items-start gap-2.5">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden className="mt-px shrink-0">
        <rect width="32" height="32" rx="7" fill="#1a1a1f" />
        <rect x="8" y="9" width="16" height="2.5" rx="1.25" fill="#F4F4F5" />
        <rect x="8" y="14.75" width="10" height="2.5" rx="1.25" fill="#F4F4F5" />
        <circle cx="22.5" cy="16" r="2.5" fill="#FF4F00" />
        <rect x="8" y="20.5" width="16" height="2.5" rx="1.25" fill="#F4F4F5" />
      </svg>
      <span className="flex flex-col leading-tight">
        <span className="title text-[15px] tracking-[-0.03em] text-rail-ink">Holdout</span>
        <span className="text-[10.5px] text-rail-muted">Offers only where they change the outcome.</span>
      </span>
    </div>
  )
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { data: ks } = useKillswitch()
  const { data: health } = useHealth()
  return (
    <aside className="flex h-full w-[212px] shrink-0 flex-col border-r border-rail-line bg-rail text-rail-ink">
      <div className="flex min-h-12 items-center px-4 py-3">
        <Wordmark />
      </div>
      <nav aria-label="Main" className="flex-1 px-2 py-2">
        <ul className="space-y-0.5">
          {NAV.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'relative flex h-8 items-center gap-2.5 rounded-[6px] px-2.5 text-[13px] transition-colors',
                    isActive ? 'bg-white/[0.06] text-rail-ink' : 'text-rail-muted hover:bg-white/[0.04] hover:text-rail-ink',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive ? <span aria-hidden className="absolute -left-2 top-1.5 bottom-1.5 w-[3px] rounded-r bg-signal" /> : null}
                    <Icon className="size-4" aria-hidden />
                    {label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="space-y-2 border-t border-rail-line px-4 py-3 text-[12px]">
        <div className="flex items-center gap-2" role="status">
          <span
            aria-hidden
            className={cn('size-2 rounded-full', !ks ? 'bg-rail-muted' : ks.on ? 'bg-[#F87171]' : 'bg-rail-ink ring-2 ring-white/15')}
          />
          <span className="text-rail-muted">
            Sending <b className="font-medium text-rail-ink">{ks ? (ks.on ? 'paused (kill switch on)' : 'live') : '…'}</b>
          </span>
        </div>
        <div className="num text-[11px] text-rail-muted">
          {USE_MOCKS ? 'mock data' : 'live API'}{health?.version ? ` · v${health.version}` : ''}
        </div>
      </div>
    </aside>
  )
}
