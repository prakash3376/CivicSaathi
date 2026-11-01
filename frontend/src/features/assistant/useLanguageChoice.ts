import { useCallback, useState } from 'react'
import type { LanguageChoice } from '@/api/types'

const STORAGE_KEY = 'civicsaathi.language'

function isChoice(value: string | null): value is LanguageChoice {
  return value === 'auto' || value === 'en' || value === 'bn' || value === 'hi'
}

function read(): LanguageChoice {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return isChoice(stored) ? stored : 'auto'
  } catch {
    return 'auto' // storage can be blocked (a private window, strict settings)
  }
}

/** The language the user picked, remembered between visits. Only this one choice is stored. */
export function useLanguageChoice(): [LanguageChoice, (choice: LanguageChoice) => void] {
  const [choice, setChoice] = useState<LanguageChoice>(read)
  const update = useCallback((next: LanguageChoice) => {
    setChoice(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Not remembered this time; the page still works.
    }
  }, [])
  return [choice, update]
}
