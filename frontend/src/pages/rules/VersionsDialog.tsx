import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { api } from '@/lib/api'
import { usePasscode } from '@/lib/hooks'
import type { Rule } from '@/lib/types'
import { formatDateTime } from '@/lib/utils'

/** Every saved version of one rule, newest first, with one-click revert. */
export function VersionsDialog({ rule, open, onOpenChange }: { rule: Rule; open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient()
  const { unlocked } = usePasscode()
  const versions = useQuery({ queryKey: ['rules', 'versions', rule.id, rule.version], queryFn: () => api.ruleVersions(rule.id), enabled: open })
  const revert = useMutation({
    mutationFn: (v: number) => api.revertRule(rule.id, v),
    onSuccess: (r, v) => {
      toast(`Reverted to v${v}: now saved as v${r.version}`)
      qc.invalidateQueries({ queryKey: ['rules'] })
      onOpenChange(false)
    },
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[min(94vw,560px)]"
        title={`History of ${rule.id}`}
        description="A revert saves the old values as a new version, so nothing is ever lost."
      >
        <ol className="max-h-[55vh] divide-y divide-line overflow-y-auto rounded-[8px] border border-line">
          {versions.isLoading ? <li className="p-3 text-[13px] text-muted">Loading…</li> : null}
          {(versions.data ?? []).map((v, i) => (
            <li key={`${v.version}-${i}`} className="flex items-start gap-3 p-3 text-[13px]">
              <span className="num w-8 shrink-0 text-muted">v{v.version}</span>
              <div className="min-w-0 flex-1">
                <p className="text-ink">{v.description}</p>
                <p className="num mt-0.5 text-[11.5px] text-muted">
                  {formatDateTime(v.updated_at)} · {v.updated_by}
                  {v.enabled ? '' : ' · off'}
                </p>
              </div>
              {i === 0 ? (
                <span className="shrink-0 text-[12px] text-muted">current</span>
              ) : (
                <Button size="sm" disabled={!unlocked || revert.isPending} onClick={() => revert.mutate(v.version)}>
                  Revert
                </Button>
              )}
            </li>
          ))}
        </ol>
        {!unlocked ? <p className="mt-3 text-[12px] text-amber-text">⚠ Unlock edits with the admin passcode to revert.</p> : null}
      </DialogContent>
    </Dialog>
  )
}
