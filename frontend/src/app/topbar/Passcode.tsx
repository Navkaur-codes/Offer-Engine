import { Lock, LockOpen } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { usePasscode } from '@/lib/hooks'

/** Unlocks writes; the passcode is kept in sessionStorage and sent as X-Admin-Passcode. */
export function Passcode() {
  const { unlocked, set } = usePasscode()
  const [draft, setDraft] = useState('')
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" aria-label={unlocked ? 'Edits unlocked. Click to lock.' : 'Read-only. Click to enter the admin passcode.'}>
          {unlocked ? <LockOpen /> : <Lock />}
          <span className="hidden xl:inline">{unlocked ? 'Editing' : 'Read-only'}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent>
        {unlocked ? (
          <div className="space-y-3">
            <p className="text-[13px]">Edits are unlocked for this browser tab.</p>
            <Button className="w-full" onClick={() => { set(null); setOpen(false) }}>Lock again</Button>
          </div>
        ) : (
          <form
            className="space-y-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (!draft.trim()) return
              set(draft.trim())
              setDraft('')
              setOpen(false)
            }}
          >
            <label htmlFor="admin-passcode" className="text-[13px] font-medium">Admin passcode</label>
            <Input id="admin-passcode" type="password" autoComplete="off" value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
            <p className="text-[12px] text-muted">Needed to change rules, festivals or the kill switch. Viewing stays open to everyone.</p>
            <Button type="submit" variant="primary" className="w-full">Unlock edits</Button>
          </form>
        )}
      </PopoverContent>
    </Popover>
  )
}
