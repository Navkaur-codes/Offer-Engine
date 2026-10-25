import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AppShell } from './app/AppShell'
import { TooltipProvider } from './components/ui/tooltip'
import { useTheme } from './lib/hooks'
import { NotFound } from './pages/Placeholder'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 15_000, refetchOnWindowFocus: false, retry: 1 } },
})

// Each page (and its charts) is its own chunk, loaded on first visit.
const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { index: true, lazy: async () => ({ Component: (await import('./pages/Overview')).Overview }) },
      { path: 'decisions', lazy: async () => ({ Component: (await import('./pages/Decisions')).Decisions }) },
      { path: 'rules', lazy: async () => ({ Component: (await import('./pages/Rules')).Rules }) },
      { path: 'realism', lazy: async () => ({ Component: (await import('./pages/Realism')).Realism }) },
      { path: 'festivals', lazy: async () => ({ Component: (await import('./pages/Festivals')).Festivals }) },
      { path: 'experiments', lazy: async () => ({ Component: (await import('./pages/Experiments')).Experiments }) },
      { path: 'playground', lazy: async () => ({ Component: (await import('./pages/Playground')).Playground }) },
      { path: 'customers', lazy: async () => ({ Component: (await import('./pages/Customers')).Customers }) },
      { path: '*', element: <NotFound /> },
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
