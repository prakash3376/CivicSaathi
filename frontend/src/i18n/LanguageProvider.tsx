import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { LanguageContext } from './LanguageContext'
import type { UiLanguage } from './translator'

const STORAGE_KEY = 'civicsaathi.ui-language'

function isLanguage(value: string | null): value is UiLanguage {
  return value === 'en' || value === 'bn' || value === 'hi'
}

function initial(): UiLanguage {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isLanguage(stored)) return stored
  } catch {
    // Storage can be blocked (a private window, strict settings): fall through to the browser.
  }
  const browser = navigator.language.toLowerCase()
  if (browser.startsWith('bn')) return 'bn'
  return browser.startsWith('hi') ? 'hi' : 'en'
}

/**
 * Holds the language of the interface, remembered between visits (this is the only thing the
 * provider stores) and written to `<html lang>` so screen readers pick the right voice.
 */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<UiLanguage>(initial)

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  const setLanguage = useCallback((next: UiLanguage) => {
    setLanguageState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Not remembered this time; the page still works.
    }
  }, [])

  const value = useMemo(() => ({ language, setLanguage }), [language, setLanguage])
  return <LanguageContext value={value}>{children}</LanguageContext>
}
