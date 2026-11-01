import { useMemo } from 'react'
import { useLanguage } from '@/i18n/LanguageContext'
import { translator } from './strings'

/**
 * What is shown while the first page of a visit is still being fetched (a bookmarked address of a
 * page that loads lazily). It names the wait, in the language of the visitor, and gives a screen
 * reader something to announce, instead of a blank page.
 */
export function LoadingFrame() {
  const { language } = useLanguage()
  const t = useMemo(() => translator(language), [language])
  return (
    <div lang={language} className="grid min-h-dvh place-items-center p-8">
      <output className="text-lg text-muted">{t('loading')}</output>
    </div>
  )
}
