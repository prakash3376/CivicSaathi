import type { UiLanguage } from './strings'

const formats: Record<UiLanguage, Intl.DateTimeFormat> = {
  en: new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }),
  // The month is spelled out in Bengali; "-u-nu-latn" keeps the digits 0-9, as the answers use.
  bn: new Intl.DateTimeFormat('bn-IN-u-nu-latn', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }),
  hi: new Intl.DateTimeFormat('hi-IN-u-nu-latn', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }),
}

/**
 * "28 Apr 2026" (or "28 এপ্রিল, 2026") from an ISO date or time, or '' if there is none. Always in
 * UTC and with digits 0-9, so a document dated the 28th is never shown as the 27th to someone
 * west of Greenwich.
 */
export function formatDate(iso: string | null, language: UiLanguage = 'en'): string {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '' : formats[language].format(date)
}
