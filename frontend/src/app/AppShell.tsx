import * as D from '@radix-ui/react-dialog'
import { Menu, Moon, Search, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { DecisionDrawer } from '@/components/DecisionDrawer'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/lib/hooks'
import { CommandPalette } from './CommandPalette'
import { Sidebar } from './Sidebar'
import { BotLink } from './topbar/BotLink'
import { BudgetMeter } from './topbar/BudgetMeter'
import { KillSwitch } from './topbar/KillSwitch'
import { Passcode } from './topbar/Passcode'
import { UpcomingMoments } from './topbar/UpcomingMoments'

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

export function AppShell() {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [killOpen, setKillOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const { theme, toggle } = useTheme()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="flex h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-[6px] focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <div className="hidden md:block">
        <Sidebar />
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-surface px-3 md:px-4">
          <D.Root open={menuOpen} onOpenChange={setMenuOpen}>
            <D.Trigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation">
                <Menu />
              </Button>
            </D.Trigger>
            <D.Portal>
              <D.Overlay className="fixed inset-0 z-50 bg-black/50 md:hidden" />
              <D.Content className="fixed inset-y-0 left-0 z-50 md:hidden" aria-describedby={undefined}>
                <D.Title className="sr-only">Navigation</D.Title>
                <Sidebar onNavigate={() => setMenuOpen(false)} />
              </D.Content>
            </D.Portal>
          </D.Root>
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex h-8 min-w-0 flex-1 items-center gap-2 rounded-[6px] border border-line bg-bg px-2.5 text-[13px] text-muted hover:border-muted md:max-w-80"
            aria-keyshortcuts="Control+K Meta+K"
          >
            <Search className="size-3.5 shrink-0" aria-hidden />
            <span className="truncate">Find customer, decision, rule…</span>
            <kbd className="num ml-auto hidden rounded-[4px] border border-line px-1 text-[11px] sm:inline">{isMac ? '⌘' : 'Ctrl'} K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-1.5">
            <UpcomingMoments />
            <div className="hidden sm:block">
              <BudgetMeter />
            </div>
            <KillSwitch open={killOpen} onOpenChange={setKillOpen} />
            <span className="hidden sm:contents">
              <BotLink />
              <Passcode />
            </span>
            <Button variant="ghost" size="icon" onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
              {theme === 'dark' ? <Sun /> : <Moon />}
            </Button>
          </div>
        </header>
        <main id="main" className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <DecisionDrawer />
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} onKillSwitch={() => setKillOpen(true)} />
    </div>
  )
}
