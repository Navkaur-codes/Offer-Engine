import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import type { NavItem } from '@/app/nav'

export function Placeholder({ item, phase }: { item: NavItem; phase: string }) {
  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 md:p-6">
      <PageHeader title={item.label} why={item.why} />
      <EmptyState
        title={`${item.label} arrives in ${phase}`}
        hint="The shell, theme and shared components are ready; this page gets wired to the API next."
        action={<Button asChild><Link to="/decisions">See decisions meanwhile</Link></Button>}
      />
    </div>
  )
}
