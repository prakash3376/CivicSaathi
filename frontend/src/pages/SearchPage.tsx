import { Link, useSearchParams } from 'react-router'
import { LoadNotice } from '@/components/ui/LoadNotice'
import { primaryButton } from '@/components/ui/buttonStyles'
import { useSources } from '@/features/assistant/useSources'
import { DocumentCard } from '@/features/portal/DocumentCard'
import { documentMatches } from '@/features/portal/documents'
import { SearchBox } from '@/features/portal/SearchBox'
import { usePortalText } from '@/features/portal/usePortalText'
import { useBudget, useSchemes } from '@/features/schemes/hooks'
import { SchemeCard } from '@/features/schemes/SchemeCard'
import { useSchemeText } from '@/features/schemes/useSchemeText'
import { matchingSectors } from '@/features/sectors/matchSectors'
import { SectorCard } from '@/features/sectors/SectorCard'
import { budgetOf, inSector } from '@/features/sectors/sectorSources'
import { filterSchemes, NO_FILTERS } from '@/features/sectors/searchSchemes'
import { useSectorText } from '@/features/sectors/useSectorText'

/**
 * What a word or a question finds across the product: sectors, schemes and official documents.
 * It is a plain match on words, not an answer. The Ask button beside it is for a real question.
 */
export function SearchPage() {
  const { language, t } = usePortalText()
  const { t: sectorT } = useSectorText()
  const { t: schemeT } = useSchemeText()
  const [params] = useSearchParams()
  const q = (params.get('q') ?? '').trim()
  const schemes = useSchemes()
  const sources = useSources()
  const budget = useBudget()

  const foundSectors = matchingSectors(sectorT, q)
  const foundSchemes = schemes.data
    ? filterSchemes(schemes.data, { ...NO_FILTERS, text: q }, language)
    : []
  const foundDocuments = sources.data?.filter((source) => documentMatches(source, q)) ?? []
  const failed = schemes.error ?? sources.error
  const loading = schemes.isPending || sources.isPending
  const nothing = foundSectors.length + foundSchemes.length + foundDocuments.length === 0

  return (
    <div lang={language} className="space-y-8">
      <title>{`${t('resultsTitle')} \u{B7} CivicSaathi`}</title>

      <section className="space-y-4">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('resultsTitle')}</h1>
        {/* Keyed by the search, so a new search starts the box from its words. */}
        <SearchBox key={q} t={t} initial={q} />
      </section>

      {q === '' ? (
        <p className="text-muted">{t('resultsEmptyQuery')}</p>
      ) : (
        <>
          <h2 className="text-xl font-semibold">{t('resultsFor', { q })}</h2>

          <section
            aria-labelledby="ask-heading"
            className="space-y-3 rounded-2xl bg-brand-soft p-5"
          >
            <h3 id="ask-heading" className="text-lg font-bold">
              {t('resultsAskTitle')}
            </h3>
            <p className="max-w-prose text-muted">{t('resultsAskText')}</p>
            <Link to={`/ask?q=${encodeURIComponent(q)}`} className={primaryButton}>
              {t('askButton')}
            </Link>
          </section>

          {failed ? (
            <LoadNotice
              error={failed}
              loadingText={t('resultsLoading')}
              failureText={t('resultsError')}
              retryLabel={t('tryAgain')}
              referenceText={(id) => t('reference', { id })}
              onRetry={() => {
                void schemes.refetch()
                void sources.refetch()
              }}
              retrying={schemes.isFetching || sources.isFetching}
            />
          ) : loading ? (
            <output className="block text-muted">{t('resultsLoading')}</output>
          ) : nothing ? (
            <div className="space-y-3 rounded-2xl border border-line bg-surface p-5">
              <p className="font-semibold">{t('resultsNone', { q })}</p>
              <p className="max-w-prose text-muted">{t('resultsNoneHelp')}</p>
              <Link
                to="/schemes"
                className="inline-flex min-h-12 items-center text-brand underline"
              >
                {t('browseSectors')}
              </Link>
            </div>
          ) : (
            <>
              {foundSectors.length > 0 && (
                <section aria-labelledby="found-sectors" className="space-y-3">
                  <h3 id="found-sectors" className="text-xl font-semibold">
                    {t('resultsSectors')}
                  </h3>
                  <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {foundSectors.map((id) => (
                      <SectorCard
                        key={id}
                        id={id}
                        t={sectorT}
                        count={schemes.data ? inSector(schemes.data, id).length : null}
                        records={budget.data ? budgetOf(budget.data, id).length : 0}
                      />
                    ))}
                  </ul>
                </section>
              )}
              {foundSchemes.length > 0 && (
                <section aria-labelledby="found-schemes" className="space-y-3">
                  <h3 id="found-schemes" className="text-xl font-semibold">
                    {t('resultsSchemes')}
                  </h3>
                  <ul className="grid gap-4 md:grid-cols-2">
                    {foundSchemes.map((scheme) => (
                      <SchemeCard key={scheme.id} scheme={scheme} t={schemeT} />
                    ))}
                  </ul>
                </section>
              )}
              {foundDocuments.length > 0 && (
                <section aria-labelledby="found-documents" className="space-y-3">
                  <h3 id="found-documents" className="text-xl font-semibold">
                    {t('resultsDocuments')}
                  </h3>
                  <ul className="grid gap-3 md:grid-cols-2">
                    {foundDocuments.map((source) => (
                      <DocumentCard key={source.id} source={source} t={t} />
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
