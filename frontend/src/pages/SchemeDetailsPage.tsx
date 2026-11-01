import { Link, useParams } from 'react-router'
import { ApiError } from '@/api/client'
import { LoadNotice } from '@/components/ui/LoadNotice'
import { useScheme } from '@/features/schemes/hooks'
import { ProgrammeDetailsView } from '@/features/schemes/ProgrammeDetailsView'
import { SchemeDetailsView } from '@/features/schemes/SchemeDetailsView'
import { useSchemeText } from '@/features/schemes/useSchemeText'

export function SchemeDetailsPage() {
  const { schemeId = '' } = useParams()
  const { language, t } = useSchemeText()
  const query = useScheme(schemeId)
  const missing = query.error instanceof ApiError && query.error.code === 'scheme_not_found'

  return (
    <div lang={language} className="space-y-6">
      <title>{`${query.data?.name ?? t('catalogueTitle')} · CivicSaathi`}</title>
      <Link to="/schemes" className="inline-flex min-h-12 items-center text-brand underline">
        {t('backToSchemes')}
      </Link>

      {query.isSuccess ? (
        // Keyed by scheme so that moving between schemes starts again from the first course.
        query.data.layout === 'info' ? (
          <ProgrammeDetailsView key={query.data.id} scheme={query.data} t={t} />
        ) : (
          <SchemeDetailsView key={query.data.id} scheme={query.data} t={t} />
        )
      ) : missing ? (
        <section className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">{t('notFoundHeading')}</h1>
          <p className="text-muted">{t('notFoundText')}</p>
        </section>
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
    </div>
  )
}
