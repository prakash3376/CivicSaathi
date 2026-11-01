import { LoadNotice } from '@/components/ui/LoadNotice'
import { useBudget, useSchemes } from '@/features/schemes/hooks'
import { useSchemeText } from '@/features/schemes/useSchemeText'
import { SchemeBrowser } from '@/features/sectors/SchemeBrowser'
import { SectorGrid } from '@/features/sectors/SectorGrid'
import { useSectorText } from '@/features/sectors/useSectorText'

/**
 * Explore schemes: the twelve sectors, and below them every verified scheme with search and the
 * Central/State and state filters. The scholarship schemes are here, and in their sector.
 */
export function SchemesPage() {
  const { language, t } = useSectorText()
  const { t: schemeT } = useSchemeText()
  const query = useSchemes()
  const budget = useBudget()

  return (
    <div lang={language} className="space-y-10">
      <title>{`${t('exploreTitle')} \u{B7} CivicSaathi`}</title>

      <section className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('exploreTitle')}</h1>
        <p className="max-w-prose text-lg text-muted">{t('exploreIntro')}</p>
      </section>

      <section aria-labelledby="sectors-heading" className="space-y-4">
        <h2 id="sectors-heading" className="text-2xl font-bold tracking-tight">
          {t('sectorsHeading')}
        </h2>
        <SectorGrid schemes={query.data} budget={budget.data} t={t} />
      </section>

      <section aria-labelledby="all-heading" className="space-y-4">
        <h2 id="all-heading" className="text-2xl font-bold tracking-tight">
          {t('allSchemesHeading')}
        </h2>
        {query.isSuccess ? (
          <SchemeBrowser
            schemes={query.data}
            t={t}
            schemeT={schemeT}
            empty={<p className="text-muted">{t('emptyTitle')}</p>}
          />
        ) : (
          <LoadNotice
            error={query.error}
            loadingText={t('loading')}
            failureText={t('loadError')}
            retryLabel={t('tryAgain')}
            referenceText={(id) => t('reference', { id })}
            onRetry={() => void query.refetch()}
            retrying={query.isFetching}
          />
        )}
      </section>
    </div>
  )
}
