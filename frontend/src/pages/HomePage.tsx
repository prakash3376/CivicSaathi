import { Link } from 'react-router'
import { LoadNotice } from '@/components/ui/LoadNotice'
import { secondaryButton } from '@/components/ui/buttonStyles'
import { useSources } from '@/features/assistant/useSources'
import { DocumentCard } from '@/features/portal/DocumentCard'
import { latestUpdates } from '@/features/portal/documents'
import { SearchBox } from '@/features/portal/SearchBox'
import { usePortalText } from '@/features/portal/usePortalText'
import { useBudget, useSchemes } from '@/features/schemes/hooks'
import { SchemeCard } from '@/features/schemes/SchemeCard'
import { useSchemeText } from '@/features/schemes/useSchemeText'
import { SectorGrid } from '@/features/sectors/SectorGrid'
import { featuredSchemes } from '@/features/sectors/sectorSources'
import { useSectorText } from '@/features/sectors/useSectorText'

const FEATURED = 6
const UPDATES = 3

/**
 * The gateway: one search box for everything, the twelve sectors, a few verified schemes, the
 * latest official documents and how the product works. Everything shown comes from the real
 * catalogue and the indexed documents; what has no data yet says so instead of being filled in.
 */
export function HomePage() {
  const { language, t } = usePortalText()
  const { t: sectorT } = useSectorText()
  const { t: schemeT } = useSchemeText()
  const schemes = useSchemes()
  const sources = useSources()
  const budget = useBudget()

  const steps = [
    { title: t('step1Title'), text: t('step1Text') },
    { title: t('step2Title'), text: t('step2Text') },
    { title: t('step3Title'), text: t('step3Text') },
  ]
  const updates = sources.data ? latestUpdates(sources.data).slice(0, UPDATES) : []

  return (
    <div lang={language} className="space-y-14">
      <title>{`CivicSaathi \u{2013} ${t('tagline')}`}</title>

      <section
        aria-labelledby="hero-heading"
        className="space-y-5 rounded-3xl bg-brand-soft p-5 sm:p-8"
      >
        <p className="font-medium text-brand">{t('tagline')}</p>
        <h1 id="hero-heading" className="max-w-3xl text-3xl font-bold tracking-tight sm:text-5xl">
          {t('heroTitle')}
        </h1>
        <p className="max-w-prose text-lg text-muted">{t('heroText')}</p>
        <SearchBox t={t} showExamples />
        <p className="max-w-prose text-sm text-muted">{t('trustNote')}</p>
      </section>

      <section aria-labelledby="sectors-heading" className="space-y-5">
        <div className="space-y-2">
          <h2 id="sectors-heading" className="text-2xl font-bold tracking-tight">
            {t('sectorsHeading')}
          </h2>
          <p className="max-w-prose text-muted">{t('sectorsIntro')}</p>
        </div>
        <SectorGrid schemes={schemes.data} budget={budget.data} t={sectorT} />
      </section>

      <section aria-labelledby="featured-heading" className="space-y-5">
        <div className="space-y-2">
          <h2 id="featured-heading" className="text-2xl font-bold tracking-tight">
            {t('featuredHeading')}
          </h2>
          <p className="max-w-prose text-muted">{t('featuredIntro')}</p>
        </div>
        {schemes.isSuccess ? (
          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {featuredSchemes(schemes.data, FEATURED).map((scheme) => (
              <SchemeCard key={scheme.id} scheme={scheme} t={schemeT} />
            ))}
          </ul>
        ) : (
          <LoadNotice
            error={schemes.error}
            loadingText={schemeT('loading')}
            failureText={schemeT('loadError')}
            retryLabel={schemeT('tryAgain')}
            referenceText={(id) => schemeT('reference', { id })}
            onRetry={() => void schemes.refetch()}
            retrying={schemes.isFetching}
          />
        )}
        <Link to="/schemes" className={secondaryButton}>
          {t('seeAllSchemes')}
        </Link>
      </section>

      <section aria-labelledby="updates-heading" className="space-y-5">
        <div className="space-y-2">
          <h2 id="updates-heading" className="text-2xl font-bold tracking-tight">
            {t('updatesHeading')}
          </h2>
          <p className="max-w-prose text-muted">{t('updatesIntro')}</p>
        </div>
        {sources.isSuccess ? (
          updates.length > 0 ? (
            <ul className="grid gap-4 md:grid-cols-2">
              {updates.map((source) => (
                <DocumentCard key={source.id} source={source} t={t} />
              ))}
            </ul>
          ) : (
            <p className="rounded-2xl border border-line bg-surface p-5 text-muted">
              {t('updatesEmpty')}
            </p>
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

      <section aria-labelledby="how-heading" className="space-y-5">
        <h2 id="how-heading" className="text-2xl font-bold tracking-tight">
          {t('howHeading')}
        </h2>
        <ol className="grid gap-4 md:grid-cols-3">
          {steps.map((step, index) => (
            <li
              key={step.title}
              className="flex gap-4 rounded-2xl border border-line bg-surface p-5"
            >
              <span
                aria-hidden="true"
                className="grid size-10 shrink-0 place-items-center rounded-full bg-brand text-lg font-bold text-white"
              >
                {index + 1}
              </span>
              <div className="space-y-1">
                <h3 className="text-lg font-semibold">{step.title}</h3>
                <p className="text-muted">{step.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
