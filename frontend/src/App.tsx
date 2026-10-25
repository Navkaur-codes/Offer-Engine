import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AppShell } from './app/AppShell'
import { NAV } from './app/nav'
import { TooltipProvider } from './components/ui/tooltip'
import { useTheme } from './lib/hooks'
import { Customers } from './pages/Customers'
import { Decisions } from './pages/Decisions'
import { Overview } from './pages/Overview'
import { Placeholder } from './pages/Placeholder'
import { Rules } from './pages/Rules'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 15_000, refetchOnWindowFocus: false, retry: 1 } },
})

const PHASE: Record<string, string> = {
 '/experiments': 'v1.0', '/festivals': 'v1.0', '/realism': 'v1.0', '/playground': 'v1.0',
}

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { index: true, element: <Overview /> },
      { path: 'decisions', element: <Decisions /> },
      { path: 'rules', element: <Rules /> },
      { path: 'customers', element: <Customers /> },
      ...NAV.filter((n) => PHASE[n.to]).map((n) => ({ path: n.to.slice(1), element: <Placeholder item={n} phase={PHASE[n.to]} /> })),
      { path: '*', element: <Placeholder item={{ ...NAV[0], label: 'Page not found', why: 'This address does not exist.' }} phase="no release" /> },
    ],
  },
])

export default function App() {
  const { theme } = useTheme()
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={200}>
        <RouterProvider router={router} />
        <Toaster theme={theme} position="bottom-right" toastOptions={{ className: 'font-sans !rounded-[8px] !border-line' }} />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
