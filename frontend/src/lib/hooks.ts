import { useCallback, useSyncExternalStore } from 'react'
import { passcode } from './api'

type Theme = 'light' | 'dark'
const THEME_KEY = 'oe-theme'

function subscribeTheme(cb: () => void) {
  const obs = new MutationObserver(cb)
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
  return () => obs.disconnect()
}
const readTheme = (): Theme => (document.documentElement.classList.contains('dark') ? 'dark' : 'light')

export function setTheme(t: Theme) {
  document.documentElement.classList.toggle('dark', t === 'dark')
  try {
    localStorage.setItem(THEME_KEY, t)
  } catch {
    /* theme still applies for this page view */
  }
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribeTheme, readTheme)
  const toggle = useCallback(() => setTheme(readTheme() === 'dark' ? 'light' : 'dark'), [])
  return { theme, toggle }
}

function subscribePasscode(cb: () => void) {
  window.addEventListener('oe-passcode', cb)
  return () => window.removeEventListener('oe-passcode', cb)
}

/** Admin passcode lives in sessionStorage; writes are disabled without it. */
export function usePasscode() {
  const value = useSyncExternalStore(subscribePasscode, passcode.get)
  return { unlocked: Boolean(value), set: passcode.set }
}
