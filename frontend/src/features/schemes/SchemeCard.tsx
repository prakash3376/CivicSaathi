import { Link } from 'react-router'
import type { EntryKind, EntryStatus, SchemeSummary } from '@/api/types'
import { primaryButton, secondaryButton } from '@/components/ui/buttonStyles'
import { local } from '@/i18n/translator'
import { DeadlineLine } from './DeadlineLine'
import { levelText } from './levelText'
import type { StringKey, Translate } from './strings'

const KIND: Record<EntryKind, StringKey> = {
  scheme: 'kindScheme',
  service: 'kindService',
  infrastructure: 'kindInfrastructure',
}

const STATUS: Record<Exclude<EntryStatus, 'active'>, StringKey> = {
  closed: 'statusClosed',
  discontinued: 'statusDiscontinued',
  merged: 'statusMerged',
}

const badge = 'rounded-md px-2 py-0.5 text-sm font-medium'

/** The kind of programme and, when it is not running, why not: in words, never by color alone. */
export function KindBadges({
  kind,
  status,
  t,
}: {
  kind: EntryKind
  status: EntryStatus
  t: Translate
}) {
  return (
    <p className="flex flex-wrap gap-2">
      <span className={`${badge} bg-brand-soft text-brand`}>{t(KIND[kind])}</span>
      {status !== 'active' && (
        <span className={`${badge} bg-warn-surface text-warn`}>{t(STATUS[status])}</span>
      )}
    </p>
  )
}

/**
 * One programme in a catalogue: who runs it, what it is, what it gives, when it closes, and where
 * to go next. The same card serves a scheme with an eligibility check (shown with its courses or
 * groups) and a programme or service that is simply read (shown with who it is for and its first
 * verified benefit). "Check if I am eligible" appears only where there is a check.
 */
export function SchemeCard({ scheme, t }: { scheme: SchemeSummary; t: Translate }) {
  const info = scheme.layout === 'info'
  return (
    <li>
      <article className="flex h-full flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
        <div className="space-y-1">
          {info && <KindBadges kind={scheme.kind} status={scheme.status} t={t} />}
          <h2 className="text-xl font-semibold">{scheme.name}</h2>
          <p className="text-sm text-muted">
            {scheme.authority} · {levelText(scheme, t)}
          </p>
        </div>
        <p className="max-w-prose">{local(scheme.summary, t.language)}</p>
        {scheme.deadline && <DeadlineLine deadline={scheme.deadline} t={t} />}
        {info && scheme.target && (
          <div className="space-y-1">
            <p className="text-sm text-muted">{t('whoFor')}</p>
            <p>{local(scheme.target, t.language)}</p>
          </div>
        )}
        {info && scheme.benefit && (
          <div className="space-y-1">
            <p className="text-sm text-muted">{t('benefitLabel')}</p>
            <p lang="en">{scheme.benefit}</p>
          </div>
        )}
        {scheme.tracks.length > 0 && (
          <div className="space-y-1">
            <p className="text-sm text-muted">{t('coursesLabel')}</p>
            <ul className="flex flex-wrap gap-2">
              {scheme.tracks.map((track) => (
                <li
                  key={track.id}
                  className="rounded-lg bg-brand-soft px-3 py-1 text-sm text-brand"
                >
                  {local(track.label, t.language)}
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="mt-auto flex flex-wrap gap-3 pt-2">
          <Link to={`/schemes/${scheme.id}`} className={primaryButton}>
            {t('viewScheme')}
            <span className="sr-only">: {scheme.name}</span>
          </Link>
          {!info && (
            <Link to={`/schemes/${scheme.id}/check`} className={secondaryButton}>
              {t('checkEligibility')}
              <span className="sr-only">: {scheme.name}</span>
            </Link>
          )}
        </div>
      </article>
    </li>
  )
}
