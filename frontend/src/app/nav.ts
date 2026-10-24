import {
  Activity, BarChart3, CalendarDays, FlaskConical, LayoutGrid, ListChecks, type LucideIcon, Play, Users,
} from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  why: string
}

export const NAV: NavItem[] = [
  { to: '/', label: 'Overview', icon: LayoutGrid, why: 'See in 10 seconds whether offers are making money that would not have come in anyway.' },
  { to: '/decisions', label: 'Decisions', icon: Activity, why: 'Every offer the engine sent, held back or blocked, with the plain-English reason why.' },
  { to: '/rules', label: 'Rules', icon: ListChecks, why: 'Set the limits the AI must stay inside. Change a number, preview the impact, then save.' },
  { to: '/customers', label: 'Customers', icon: Users, why: 'Who is in which policy right now, and what the engine would do for any one of them.' },
  { to: '/experiments', label: 'Experiments', icon: FlaskConical, why: 'Proof that offers cause extra sales: treated customers vs a 10% holdout that got nothing.' },
  { to: '/festivals', label: 'Festivals', icon: CalendarDays, why: 'Plan budget and strategy for each upcoming sales moment, phase by phase.' },
  { to: '/realism', label: 'Realism', icon: BarChart3, why: 'Checks that the synthetic shoppers behave like real e-commerce data, against benchmarks.' },
  { to: '/playground', label: 'Playground', icon: Play, why: 'Run the full decision pipeline for any customer without sending anything.' },
]
