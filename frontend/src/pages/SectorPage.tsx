import { Link, useParams } from 'react-router'
import type { SectorId } from '@/api/types'
import { SectionBoundary } from '@/components/errors/SectionBoundary'
import { LoadNotice } from '@/components/ui/LoadNotice'
import { primaryButton } from '@/components/ui/buttonStyles'
import { useSources } from '@/features/assistant/useSources'
import { DocumentCard } from '@/features/portal/DocumentCard'
import { usePortalText } from '@/features/portal/usePortalText'
import { useBudget, useSchemes } from '@/features/schemes/hooks'
import { useSchemeText } from '@/features/schemes/useSchemeText'
import { BudgetSection } from '@/features/sectors/BudgetSection'
import { sectorQuestions } from '@/features/sectors/questions'
import { SchemeBrowser } from '@/features/sectors/SchemeBrowser'
import { SectorIcon } from '@/features/sectors/SectorIcon'
import { budgetOf, inSector } from '@/features/sectors/sectorSources'
import { isSectorId } from '@/features/sectors/sectors'
import { sectorText, sectorTitle, useSectorText } from '@/features/sectors/useSectorText'
import { NotFoundPage } from './NotFoundPage'

/**
 * One sector. Every sector uses this page: what differs is the data, which is the programmes the
 * catalogue lists under it, the budget records that belong to it, and the documents they rest on.
 * A sector with none says so plainly.
 */
export function SectorPage() {
  const { sectorId } = useParams()
  if (!isSectorId(sectorId)) return <NotFoundPage />
  return <Sector id={sectorId} key={sectorId} />
}

function Sector({ id }: { id: SectorId }) {
  const { language, t } = useSectorText()
  const { t: schemeT } = useSchemeText()
  const { t: portalT } = usePortalText()
  const schemes = useSchemes()
  const budget = useBudget()
  const sources = useSources()

  const title = sectorTitle(t, id)
  const mine = schemes.data ? inSector(schemes.data, id) : []
  const records = budget.data ? budgetOf(budget.data, id) : []
  const sourceIds = new Set(mine.flatMap((scheme) => scheme.source_ids))
  const documents = sources.data?.filter((source) => sourceIds.has(source.id)) ?? []
  const questions = sectorQuestions(id, language)
  const isBudget = id === 'budget'
  // The Budget sector is about budget records: it lists schemes only if it has some.
  const showSchemes = !isBudget || mine.length > 0
  const nothingAtAll = schemes.isSuccess && mine.length === 0 && records.length === 0

  const empty = (
    <div className="space-y-3 rounded-2xl border border-line bg-surface p-5">
      <p className="text-lg font-semibold">{t('emptyTitle')}</p>
      <p className="max-w-prose text-muted">{t('emptyText')}</p>
      {isBudget && <p className="max-w-prose text-muted">{t('budgetNote')}</p>}
      <Link to="/schemes" className={primaryButton}>
        {t('allSectors')}
      </Link>
    </div>
  )

  const counts = [
    mine.length === 1
      ? t('schemeCountOne')
      : mine.length > 1
        ? t('schemeCountMany', { n: mine.length })
        : '',
    records.length === 1
      ? t('budgetOne')
      : records.length > 1
        ? t('budgetShown', { n: records.length })
        : '',
  ].filter(Boolean)

  return (
    <div lang={language} className="space-y-10">
      <title>{`${title} \u{B7} CivicSaathi`}</title>
      <Link to="/schemes" className="inline-flex min-h-12 items-center text-brand underline">
        {t('allSectors')}
      </Link>

      <section aria-labelledby="sector-heading" className="flex gap-4">
        <span className="hidden size-16 shrink-0 place-items-center rounded-2xl bg-brand-soft text-brand sm:grid">
          <SectorIcon id={id} size={36} />
        </span>
        <div className="space-y-3">
          <h1 id="sector-heading" className="text-3xl font-bold tracking-tight sm:text-4xl">
            {title}
          </h1>
          <p className="max-w-prose text-lg text-muted">{sectorText(t, id)}</p>
          {mine.length > 0 && (
            <p className="max-w-prose text-sm text-muted">{t('sectorIntroNote')}</p>
          )}
          {counts.length > 0 && <p className="font-medium text-ok">{counts.join(' \u{B7} ')}</p>}
        </div>
      </section>

      {showSchemes && (
        <section aria-labelledby="schemes-heading" className="space-y-5">
          <h2 id="schemes-heading" className="text-2xl font-bold tracking-tight">
            {t('schemesInSector')}
          </h2>
          {schemes.isSuccess ? (
            <>
              {mine.some((scheme) => scheme.layout === 'check') && (
                <p className="max-w-prose text-muted">{t('checkerHint')}</p>
              )}
              <SectionBoundary>
                <SchemeBrowser schemes={mine} t={t} schemeT={schemeT} empty={empty} />
              </SectionBoundary>
            </>
          ) : (
            <LoadNotice
              error={schemes.error}
              loadingText={t('loading')}
              failureText={t('loadError')}
              retryLabel={t('tryAgain')}
              referenceText={(ref) => t('reference', { id: ref })}
              onRetry={() => void schemes.refetch()}
              retrying={schemes.isFetching}
            />
          )}
        </section>
      )}

      {(isBudget || records.length > 0 || budget.isError) && (
        <section aria-labelledby="budget-heading" className="space-y-4">
          <h2 id="budget-heading" className="text-2xl font-bold tracking-tight">
            {isBudget ? t('budgetHeading') : t('openInSector', { sector: title })}
          </h2>
          <p className="max-w-prose text-muted">{t('budgetIntro')}</p>
          {budget.isSuccess ? (
            records.length > 0 ? (
              <SectionBoundary>
                <BudgetSection records={records} t={t} schemeT={schemeT} />
              </SectionBoundary>
            ) : nothingAtAll && isBudget ? (
              empty
            ) : (
              <p className="rounded-2xl border border-line bg-surface p-5 text-muted">
                {t('budgetEmpty')}
              </p>
            )
          ) : budget.isPending ? (
            <output className="block text-muted">{t('loading')}</output>
          ) : (
            <LoadNotice
              error={budget.error}
              loadingText={t('loading')}
              failureText={t('budgetError')}
              retryLabel={t('tryAgain')}
              referenceText={(ref) => t('reference', { id: ref })}
              onRetry={() => void budget.refetch()}
              retrying={budget.isFetching}
            />
          )}
        </section>
      )}

      {documents.length > 0 && (
        <section aria-labelledby="documents-heading" className="space-y-4">
          <h2 id="documents-heading" className="text-2xl font-bold tracking-tight">
            {t('documentsTitle')}
          </h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {documents.map((source) => (
              <DocumentCard key={source.id} source={source} t={portalT} />
            ))}
          </ul>
        </section>
      )}

      {questions.length > 0 && (mine.length > 0 || records.length > 0) && (
        <section aria-labelledby="questions-heading" className="space-y-3">
          <h2 id="questions-heading" className="text-2xl font-bold tracking-tight">
            {t('questionsTitle')}
          </h2>
          <ul className="flex flex-col gap-2">
            {questions.map((question) => (
              <li key={question}>
                <Link
                  to={`/ask?sector=${id}&q=${encodeURIComponent(question)}`}
                  className="flex min-h-12 items-center rounded-xl border border-line bg-surface px-4 py-2 hover:bg-brand-soft"
                >
                  {question}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section
        aria-labelledby="ask-heading"
        className="space-y-3 rounded-2xl bg-brand-soft p-5 sm:p-6"
      >
        <h2 id="ask-heading" className="text-xl font-bold">
          {t('askSectorTitle', { sector: title })}
        </h2>
        <p className="max-w-prose text-muted">{t('askSectorText')}</p>
        <Link to={`/ask?sector=${id}`} className={primaryButton}>
          {t('askSectorButton')}
        </Link>
      </section>
    </div>
  )
}
