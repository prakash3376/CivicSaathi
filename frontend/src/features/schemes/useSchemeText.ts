import { useMemo } from 'react'
import { useLanguage } from '@/i18n/LanguageContext'
import { translator } from './strings'

/** The interface language and the scheme screens' words in it. */
export function useSchemeText() {
  const { language } = useLanguage()
  const t = useMemo(() => translator(language), [language])
  return { language, t }
}
