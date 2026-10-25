import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent } from '@/components/ui/dialog'
import { usePasscode } from '@/lib/hooks'
import { useKillswitch, useSetKillswitch } from '@/lib/queries'
import { cn, formatDateTime } from '@/lib/utils'

export function KillSwitch({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { data } = useKillswitch()
  const set = useSetKillswitch()
  const { unlocked } = usePasscode()
  const on = Boolean(data?.on)

  return (
    <>
      <button
        onClick={() => onOpenChange(true)}
        className={cn(
          'inline-flex h-8 items-center gap-2 rounded-[6px] border px-2.5 text-[13px] font-medium',
          on ? 'border-danger/50 bg-danger-soft text-danger-text' : 'border-line bg-surface text-ink hover:bg-surface-2',
        )}
        aria-label={on ? 'Sending paused: kill switch is on. Click to resume.' : 'Sending live: kill switch is off. Click to pause all sends.'}
      >
        <span aria-hidden className={cn('size-2 rounded-full', on ? 'bg-danger' : 'bg-ink')} />
        {on ? 'Sending paused' : 'Sending live'}
      </button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          title={on ? 'Resume sending offers?' : 'Pause all offers now?'}
          description={
            on
              ? 'Decisions will go back to being sent on Telegram, still checked by every rule.'
              : 'The pre-gate blocks every new offer until you switch it back. Decisions are still logged as Blocked.'
          }
        >
          {data?.changed_at ? <p className="num mb-3 text-[12px] text-muted">Last changed {formatDateTime(data.changed_at)}</p> : null}
          {!unlocked ? <p className="mb-3 text-[13px] text-amber-text">Enter the admin passcode in the top bar first.</p> : null}
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <Button variant="ghost">Cancel</Button>
            </DialogClose>
            <Button
              variant={on ? 'primary' : 'danger'}
              disabled={set.isPending || !unlocked}
              onClick={() =>
                set.mutate(!on, {
                  onSuccess: (r) => {
                    toast(r.on ? 'Kill switch ON: all sends paused' : 'Sending resumed')
                    onOpenChange(false)
                  },
                })
              }
            >
              {on ? 'Resume sending' : '✗ Pause all sends'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
