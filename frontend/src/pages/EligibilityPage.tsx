import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { ApiError } from '@/api/client'
import type { Answers } from '@/api/types'
import { LoadNotice } from '@/components/ui/LoadNotice'
import { primaryButton } from '@/components/ui/buttonStyles'
import type { RawAnswers } from '@/features/schemes/answers'
import { EligibilityForm } from '@/features/schemes/EligibilityForm'
import { useEligibilityCheck, useScheme } from '@/features/schemes/hooks'
import { fieldDomId } from '@/features/schemes/fieldIds'
import { ResultView } from '@/features/schemes/ResultView'
import { TrackPicker } from '@/features/schemes/TrackPicker'
import { useSchemeText } from '@/features/schemes/useSchemeText'

/**
 * Pick a course or group, answer what you can, and see the result with its checklist. The track is
 * in the address (`?track=ug`) so that a link can start at the right course; the answers are
 * held in memory only and are never put in the address, stored or logged.
 */
export function EligibilityPage() {
  const { schemeId = '' } = useParams()
  const [search, setSearch] = useSearchParams()
  const { language, t } = useSchemeText()
  const query = useScheme(schemeId)
  const check = useEligibilityCheck(schemeId)
  const [values, setValues] = useState<RawAnswers>({})

  const scheme = query.data?.layout === 'check' ? query.data : undefined
  const noCheck = query.data?.layout === 'info'
  const wanted = search.get('track')
  const track =
    scheme?.tracks.find((candidate) => candidate.id === wanted) ??
    (scheme?.tracks.length === 1 ? scheme.tracks[0] : undefined)
  const missing = query.error instanceof ApiError && query.error.code === 'scheme_not_found'

  function chooseTrack(id: string) {
    setSearch({ track: id }, { replace: true })
    setValues({})
    check.reset()
  }

  function change(field: string, value: string) {
    setValues((current) => ({ ...current, [field]: value }))
    check.reset() // the result would no longer match what the form shows
  }

  function submit(answers: Answers) {
    if (track) check.mutate({ track: track.id, answers })
  }

  function answerMissing() {
    const field = check.data?.unanswered[0]
    if (field) document.getElementById(fieldDomId(field))?.focus()
  }

  return (
    <div lang={language} className="space-y-8">
      <title>{`${t('checkTitle')} · CivicSaathi`}</title>
      <Link
        to={`/schemes/${schemeId}`}
        className="inline-flex min-h-12 items-center text-brand underline"
      >
        {scheme?.name ?? t('backToSchemes')}
      </Link>

      {missing ? (
        <section className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">{t('notFoundHeading')}</h1>
          <p className="text-muted">{t('notFoundText')}</p>
        </section>
      ) : noCheck ? (
        <section className="space-y-3">
          <h1 className="text-3xl font-bold tracking-tight">{t('noCheckHeading')}</h1>
          <p className="max-w-prose text-muted">{t('noCheckText')}</p>
          <Link to={`/schemes/${schemeId}`} className={primaryButton}>
            {t('viewScheme')}
          </Link>
        </section>
      ) : !scheme ? (
        <LoadNotice
          error={query.error}
          loadingText={t('loading')}
          failureText={t('loadError')}
          retryLabel={t('tryAgain')}
          referenceText={(id) => t('reference', { id })}
          onRetry={() => void query.refetch()}
          retrying={query.isFetching}
        />
      ) : (
        <>
          <section className="space-y-3">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('checkTitle')}</h1>
            <p className="text-lg font-medium">{scheme.name}</p>
            <p className="max-w-prose text-lg text-muted">{t('checkIntro')}</p>
            <p className="max-w-prose text-sm text-muted">{t('privacyNote')}</p>
          </section>

          {scheme.tracks.length > 1 && (
            <TrackPicker
              legend={t('chooseTrack')}
              tracks={scheme.tracks}
              value={track?.id ?? null}
              onChange={chooseTrack}
              language={language}
            />
          )}

          {track && (
            <section aria-labelledby="profile-heading" className="space-y-4">
              <h2 id="profile-heading" className="text-xl font-semibold">
                {t('profileHeading')}
              </h2>
              {/* Keyed by track: another course starts with a clean form. */}
              <EligibilityForm
                key={track.id}
                track={track}
                values={values}
                onChange={change}
                onSubmit={submit}
                pending={check.isPending}
                t={t}
              />
            </section>
          )}

          {check.isPending && <output className="block text-lg text-muted">{t('checking')}</output>}
          {check.isError && (
            <LoadNotice
              error={check.error}
              loadingText={t('checking')}
              failureText={t('checkError')}
              retryLabel={t('tryAgain')}
              referenceText={(id) => t('reference', { id })}
              onRetry={() => check.variables && check.mutate(check.variables)}
            />
          )}
          {track && check.isSuccess && (
            <ResultView result={check.data} track={track} t={t} onAnswerMissing={answerMissing} />
          )}
        </>
      )}
    </div>
  )
}
