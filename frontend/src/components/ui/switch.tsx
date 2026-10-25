import { cn } from '@/lib/utils'

/** Accessible on/off switch; the label is always visible text, never colour alone. */
export function Switch({
  checked, onChange, disabled, label, title,
}: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string; title?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={title}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="inline-flex items-center gap-1.5 text-[12px] text-muted disabled:cursor-not-allowed disabled:opacity-60"
    >
      <span className={cn('relative h-4 w-7 rounded-full border transition-colors', checked ? 'border-ink bg-ink' : 'border-line bg-surface-2')}>
        <span className={cn('absolute top-[1px] size-3 rounded-full transition-transform', checked ? 'translate-x-[13px] bg-bg' : 'translate-x-[1px] bg-muted')} />
      </span>
      {checked ? 'On' : 'Off'}
    </button>
  )
}
