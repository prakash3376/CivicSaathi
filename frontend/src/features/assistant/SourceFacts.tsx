import { formatDate } from './dates'
import type { Translate } from './strings'

interface Props {
  documentDate: string | null
  verifiedAt: string | null
  stale: boolean
  scanned: boolean
  /** Last verified long enough ago that it should be checked again. Not known for a citation. */
  verificationDue?: boolean
  t: Translate
}

const warnBadge = 'border-warn-line bg-warn-surface text-warn'

/**
 * How current a source is (SPEC rule R4): its date, when it was last verified, and a badge for
 * anything the reader can act on. A badge always says what it means in words.
 *
 * Not shown: the "verified with warnings" status of the ingestion checks. Those warnings are
 * either shown here in specific words (an old date, a missing date, a scan) or are technical, such
 * as how a server negotiates TLS, and a reader cannot do anything about them. A badge on every
 * source would only teach people to ignore badges. The status stays in the API data.
 */
export function SourceFacts({
  documentDate,
  verifiedAt,
  stale,
  scanned,
  verificationDue = false,
  t,
}: Props) {
  const badges: string[] = []
  if (stale) badges.push(t('staleBadge'))
  if (scanned) badges.push(t('scannedBadge'))
  if (verificationDue) badges.push(t('dueBadge'))

  const dated = formatDate(documentDate, t.language)
  const verified = formatDate(verifiedAt, t.language)
  return (
    <>
      <p className="text-sm text-muted">
        {dated ? t('dated', { date: dated }) : t('dateUnknown')}
        {' · '}
        {verified ? t('verified', { date: verified }) : t('verifiedNever')}
      </p>
      {badges.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {badges.map((label) => (
            <li key={label} className={`rounded-full border px-3 py-1 text-sm ${warnBadge}`}>
              {label}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
