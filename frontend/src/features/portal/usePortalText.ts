import { useMemo } from 'react'
import { useLanguage } from '@/i18n/LanguageContext'
import { translator } from './strings'

/** The interface language and the words of the portal pages in it. */
export function usePortalText() {
  const { language } = useLanguage()
  const t = useMemo(() => translator(language), [language])
  return { language, t }
}
