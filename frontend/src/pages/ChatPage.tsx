import { useMemo } from 'react'
import { SectionBoundary } from '@/components/errors/SectionBoundary'
import { ChatSection } from '@/features/assistant/ChatSection'
import { SourcesList } from '@/features/assistant/SourcesList'
import { translator } from '@/features/assistant/strings'
import { useLanguage } from '@/i18n/LanguageContext'

/**
 * Ask questions and get answers taken from the official documents, one after another. A question
 * may be limited to one scheme's documents (`?scheme=svmcm`), and may arrive typed
 * in the box (`?q=...`) from the search; it is never sent without the person pressing Ask. Nothing is stored: the
 * conversation is in memory and goes when the page does.
 *
 * The conversation and the list of documents are separate sections, each with its own boundary: a
 * failure to render one leaves the other, and the page's heading, in place.
 */
export function ChatPage() {
  const { language: uiLanguage } = useLanguage()
  const t = useMemo(() => translator(uiLanguage), [uiLanguage])

  return (
    <div lang={uiLanguage} className="space-y-8">
      <title>{`${t('pageTitle')} · CivicSaathi`}</title>

      <section className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('pageTitle')}</h1>
        <p className="max-w-prose text-lg text-muted">{t('intro')}</p>
        <p className="max-w-prose text-sm text-muted">{t('chatPrivacy')}</p>
      </section>

      <SectionBoundary>
        <ChatSection />
      </SectionBoundary>

      <SectionBoundary>
        <SourcesList t={t} />
      </SectionBoundary>
    </div>
  )
}
