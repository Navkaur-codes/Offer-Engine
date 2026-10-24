import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const inr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
/** ₹1,299 (Indian digit grouping). */
export const formatInr = (n: number) => `${n < 0 ? '−' : ''}₹${inr.format(Math.abs(Math.round(n)))}`
export const formatInrCompact = (n: number) => {
  const a = Math.abs(n)
  const s = a >= 1e7 ? `${(a / 1e7).toFixed(1)}Cr` : a >= 1e5 ? `${(a / 1e5).toFixed(1)}L` : a >= 1e3 ? `${(a / 1e3).toFixed(1)}k` : `${Math.round(a)}`
  return `${n < 0 ? '−' : ''}₹${s}`
}
export const formatPct = (n: number, digits = 1) => `${(n * 100).toFixed(digits)}%`
export const formatInt = (n: number) => inr.format(n)

const timeFmt = new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: false })
const dateFmt = new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short' })
export const formatTime = (iso: string) => timeFmt.format(new Date(iso))
export const formatDate = (iso: string) => dateFmt.format(new Date(iso))
export const formatDateTime = (iso: string) => `${formatDate(iso)}, ${formatTime(iso)}`

/** Whole days from `from` to an IST calendar date (YYYY-MM-DD). */
export function daysUntil(date: string, from: Date): number {
  const today = new Date(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(from))
  return Math.round((new Date(date).getTime() - today.getTime()) / 86_400_000)
}
