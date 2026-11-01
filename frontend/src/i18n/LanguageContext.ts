import { createContext, useContext } from 'react'
import type { UiLanguage } from './translator'

export interface LanguageState {
  language: UiLanguage
  setLanguage: (language: UiLanguage) => void
}

export const LanguageContext = createContext<LanguageState | null>(null)

/** The language of the interface, chosen with the switch in the header. */
export function useLanguage(): LanguageState {
  const state = useContext(LanguageContext)
  if (!state) throw new Error('useLanguage must be used inside <LanguageProvider>')
  return state
}
