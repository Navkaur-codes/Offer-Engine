import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'

export function NotFound() {
  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 md:p-6">
      <PageHeader title="Page not found" why="This address doesn’t exist in the dashboard." />
      <EmptyState
        title="Nothing here"
        hint="The link may be old. Use ⌘K to find a customer, decision or rule."
        action={<Button asChild><Link to="/">Back to Overview</Link></Button>}
      />
    </div>
  )
}
