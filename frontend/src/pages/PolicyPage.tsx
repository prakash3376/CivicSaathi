import { useId, useState } from 'react'
import { Link } from 'react-router'
import { LoadNotice } from '@/components/ui/LoadNotice'
import { primaryButton } from '@/components/ui/buttonStyles'
import { useSources } from '@/features/assistant/useSources'
import { DocumentCard } from '@/features/portal/DocumentCard'
import { documentMatches } from '@/features/portal/documents'
import { usePortalText } from '@/features/portal/usePortalText'
import { useSchemes } from '@/features/schemes/hooks'

/**
 * Policy & Rights: the official documents the product has read, each linked to the original, and
 * the way to ask questions about them. What does not exist yet (uploading a document, comparing
 * versions) is said in words and has no button, so nothing on the page does nothing.
 */
export function PolicyPage() {
  const { language, t } = usePortalText()
  const ids = useId()
  const sources = useSources()
  const schemes = useSchemes()
  const [text, setText] = useState('')

  const shown = sources.data?.filter((source) => documentMatches(source, text)) ?? []
  const schemeOf = (sourceId: string) =>
    schemes.data?.find((scheme) => scheme.source_ids.includes(sourceId))

  return (
    <div lang={language} className="space-y-10">
      <title>{`${t('policyTitle')} \u{B7} CivicSaathi`}</title>

      <section className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('policyTitle')}</h1>
        <p className="max-w-prose text-lg text-muted">{t('policyIntro')}</p>
      </section>

      <section
        aria-labelledby="policy-ask"
        className="space-y-3 rounded-2xl bg-brand-soft p-5 sm:p-6"
      >
        <h2 id="policy-ask" className="text-xl font-bold">
          {t('policyAskTitle')}
        </h2>
        <p className="max-w-prose text-muted">{t('policyAskText')}</p>
        <Link to="/ask" className={primaryButton}>
          {t('askButton')}
        </Link>
      </section>

      <section aria-labelledby="policy-library" className="space-y-4">
        <h2 id="policy-library" className="text-2xl font-bold tracking-tight">
          {t('policyLibrary')}
        </h2>

        {sources.isSuccess ? (
          sources.data.length === 0 ? (
            <p className="rounded-2xl border border-line bg-surface p-5 text-muted">
              {t('policyEmpty')}
            </p>
          ) : (
            <>
              <div className="space-y-2">
                <label htmlFor={`${ids}-q`} className="block font-medium">
                  {t('policySearch')}
                </label>
                <input
                  id={`${ids}-q`}
                  type="search"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder={t('policySearchPlaceholder')}
                  className="min-h-12 w-full max-w-xl rounded-xl border border-muted bg-surface px-3 text-ink"
                />
              </div>
              {shown.length > 0 ? (
                <ul className="grid gap-3 md:grid-cols-2">
                  {shown.map((source) => {
                    const scheme = schemeOf(source.id)
                    return (
                      <DocumentCard
                        key={source.id}
                        source={source}
                        t={t}
                        askScheme={scheme && { id: scheme.id, label: scheme.name }}
                      />
                    )
                  })}
                </ul>
              ) : (
                <p className="text-muted">{t('policyNoMatch')}</p>
              )}
            </>
          )
        ) : (
          <LoadNotice
            error={sources.error}
            loadingText={t('policyLoading')}
            failureText={t('policyError')}
            retryLabel={t('tryAgain')}
            referenceText={(id) => t('reference', { id })}
            onRetry={() => void sources.refetch()}
            retrying={sources.isFetching}
          />
        )}
      </section>

      <section
        aria-labelledby="policy-soon"
        className="space-y-3 rounded-2xl border border-warn-line bg-warn-surface p-5"
      >
        <h2 id="policy-soon" className="text-lg font-bold text-warn">
          {t('policySoonTitle')}
        </h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>{t('policySoon1')}</li>
          <li>{t('policySoon2')}</li>
        </ul>
        <p className="max-w-prose text-sm text-muted">{t('policySoonNote')}</p>
      </section>
    </div>
  )
}
