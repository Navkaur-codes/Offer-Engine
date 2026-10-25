import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Countdown } from '@/app/topbar/UpcomingMoments'
import { EmptyState } from '@/components/EmptyState'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card'
import { NAV } from '@/app/nav'
import { upcoming } from '@/lib/festivals'
import { PHASE_LABEL } from '@/lib/labels'
import { useFestivals, useMeta } from '@/lib/queries'
import { cn, formatDate } from '@/lib/utils'
import { CalendarStrip } from './festivals/CalendarStrip'
import { FestivalEditor } from './festivals/FestivalEditor'

export function Festivals() {
  const [params, setParams] = useSearchParams()
  const { data: festivals, isLoading, refetch } = useFestivals()
  const { data: meta } = useMeta()
  const [fallbackNow] = useState(() => new Date())
  const today = meta ? new Date(meta.demo_time_override ?? meta.now) : fallbackNow
  const list = upcoming(festivals ?? [], today)
  const selectedId = params.get('f') ?? list.find((x) => x.days >= 0)?.f.id
  const selected = festivals?.find((f) => f.id === selectedId)
  const select = (id: string) => setParams({ f: id }, { replace: true })

  return (
    <div className="mx-auto max-w-[1400px] space-y-4 p-4 md:p-6">
      <PageHeader title="Festivals" why={NAV[5].why} />

      {isLoading ? (
        <div className="h-48 animate-pulse rounded-[8px] bg-surface-2" />
      ) : !festivals?.length ? (
        <EmptyState title="No festivals loaded" hint="The festival calendar is seeded by the backend." action={<Button onClick={() => refetch()}>Reload</Button>} />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Next 90 days</CardTitle>
              <span className="text-[11.5px] text-muted">Click a row to edit it · the dark tick is the festival day</span>
            </CardHeader>
            <CardBody>
              <CalendarStrip festivals={festivals} today={today} selected={selectedId} onSelect={select} />
            </CardBody>
          </Card>

          <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
            <Card className="self-start">
              <CardHeader><CardTitle>Upcoming</CardTitle></CardHeader>
              <ul className="max-h-[560px] divide-y divide-line overflow-y-auto">
                {list.map(({ f, days, phase }) => (
                  <li key={f.id}>
                    <button
                      onClick={() => select(f.id)}
                      aria-current={f.id === selectedId}
                      className={cn('flex w-full items-center justify-between gap-2 px-4 py-2.5 text-left hover:bg-surface-2', f.id === selectedId && 'bg-surface-2')}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-[13px] text-ink">{f.name}</span>
                        <span className="num block text-[11.5px] text-muted">
                          {formatDate(f.date)}{phase ? ` · ${PHASE_LABEL[phase]}` : ''} · <Money value={f.budget} compact />
                        </span>
                      </span>
                      <Countdown days={days} />
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
            <Card className="p-4">
              {selected ? <FestivalEditor key={`${selected.id}-${selected.date}-${selected.budget}`} f={selected} /> : <p className="text-[13px] text-muted">Pick a festival to edit it.</p>}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
