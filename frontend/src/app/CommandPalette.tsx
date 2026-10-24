import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Command } from 'cmdk'
import * as D from '@radix-ui/react-dialog'
import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { botUrl, FALLBACK_BOT } from '@/lib/bot'
import { useTheme } from '@/lib/hooks'
import { POLICY_LABEL } from '@/lib/labels'
import { useKillswitch, useMeta } from '@/lib/queries'
import { NAV } from './nav'

export function CommandPalette({
  open, onOpenChange, onKillSwitch,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onKillSwitch: () => void
}) {
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  const { toggle, theme } = useTheme()
  const { data: meta } = useMeta()
  const { data: ks } = useKillswitch()
  const customers = useQuery({
    queryKey: ['customers', 'palette', search],
    queryFn: () => api.customers({ q: search || undefined, limit: 8 }),
    enabled: open,
    placeholderData: keepPreviousData,
  })
  const rules = useQuery({ queryKey: ['rules', 'all'], queryFn: () => api.rules(), enabled: open, staleTime: 60_000 })

  const run = (fn: () => void) => {
    onOpenChange(false)
    setSearch('')
    fn()
  }
  const decisionId = /^d[\w-]{3,}$/i.test(search.trim()) ? search.trim().toUpperCase() : null

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Command palette"
      overlayClassName="fixed inset-0 z-50 bg-black/40"
      contentClassName="fixed left-1/2 top-[14%] z-50 w-[min(94vw,580px)] -translate-x-1/2 overflow-hidden rounded-[8px] border border-line bg-surface text-ink shadow-menu"
    >
      <D.Title className="sr-only">Command palette</D.Title>
      <D.Description className="sr-only">Search customers, decisions, rules and actions</D.Description>
      <Command.Input
        value={search}
        onValueChange={setSearch}
        placeholder="Find a customer, decision ID, rule, or action…"
        className="h-12 w-full border-b border-line bg-transparent px-4 text-[14px] outline-none placeholder:text-muted"
      />
      <Command.List className="max-h-[56vh] overflow-y-auto p-1.5 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted">
        <Command.Empty className="px-3 py-6 text-center text-[13px] text-muted">No match. Try a name, C000012, or a rule word like “cap”.</Command.Empty>

        {decisionId ? (
          <Command.Group heading="Decision">
            <Item value={`open decision ${decisionId}`} onSelect={() => run(() => navigate(`/decisions?id=${encodeURIComponent(decisionId)}`))}>
              Open decision <Mono>{decisionId}</Mono>
            </Item>
          </Command.Group>
        ) : null}

        <Command.Group heading="Actions">
          <Item value="kill switch pause resume sending" onSelect={() => run(onKillSwitch)} hint={ks?.on ? 'on' : 'off'}>
            {ks?.on ? 'Resume sending (turn kill switch off)' : 'Pause all sends (kill switch)'}
          </Item>
          <Item value="campaign dry-run" onSelect={() => run(() => navigate('/customers?dryrun=1'))}>Campaign dry-run…</Item>
          <Item value="playground run decision simulate" onSelect={() => run(() => navigate('/playground'))}>Run a decision in Playground…</Item>
          <Item value="open telegram bot" onSelect={() => run(() => window.open(botUrl(meta?.bot_username ?? FALLBACK_BOT), '_blank', 'noopener'))}>
            Open the Telegram bot ↗
          </Item>
          <Item value="switch theme dark light mode" onSelect={() => run(toggle)}>
            Switch to {theme === 'dark' ? 'light' : 'dark'} theme
          </Item>
        </Command.Group>

        <Command.Group heading="Customers">
          {(customers.data?.items ?? []).map((c) => (
            <Item
              key={c.customer_id}
              value={`customer ${c.customer_id} ${c.first_name} ${POLICY_LABEL[c.policy]}`}
              onSelect={() => run(() => navigate(`/customers?id=${c.customer_id}`))}
              hint={POLICY_LABEL[c.policy]}
            >
              {c.first_name} <Mono>{c.customer_id}</Mono>
            </Item>
          ))}
          {(customers.data?.items ?? []).slice(0, 3).map((c) => (
            <Item
              key={`pg-${c.customer_id}`}
              value={`playground run for ${c.customer_id} ${c.first_name}`}
              onSelect={() => run(() => navigate(`/playground?customer=${c.customer_id}`))}
            >
              Run Playground for {c.first_name} <Mono>{c.customer_id}</Mono>
            </Item>
          ))}
        </Command.Group>

        <Command.Group heading="Edit rule">
          {(rules.data ?? []).map((r) => (
            <Item key={r.id} value={`edit rule ${r.id} ${r.description}`} onSelect={() => run(() => navigate(`/rules?rule=${r.id}`))}>
              <span className="truncate">{r.description}</span>
            </Item>
          ))}
        </Command.Group>

        <Command.Group heading="Go to">
          {NAV.map((n) => (
            <Item key={n.to} value={`go to ${n.label}`} onSelect={() => run(() => navigate(n.to))}>
              {n.label}
            </Item>
          ))}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  )
}

function Item({ children, hint, ...props }: { children: ReactNode; hint?: string; value: string; onSelect: () => void }) {
  return (
    <Command.Item
      {...props}
      className="flex h-9 cursor-pointer items-center justify-between gap-3 rounded-[6px] px-2.5 text-[13px] data-[selected=true]:bg-surface-2"
    >
      <span className="flex min-w-0 items-center gap-1.5">{children}</span>
      {hint ? <span className="shrink-0 text-[11.5px] text-muted">{hint}</span> : null}
    </Command.Item>
  )
}

const Mono = ({ children }: { children: ReactNode }) => <span className="num text-[12px] text-muted">{children}</span>
