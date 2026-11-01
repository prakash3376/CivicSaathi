import { primaryButton } from '@/components/ui/buttonStyles'
import { OfficialLink } from './OfficialLink'
import { SourceFacts } from './SourceFacts'
import type { Translate } from './strings'
import { useSources } from './useSources'

/** The documents the assistant answers from, with how current each one is (SPEC rule R4). */
export function SourcesList({ t }: { t: Translate }) {
  const query = useSources()

  let body
  if (query.isPending) {
    body = <output className="block text-muted">{t('libraryLoading')}</output>
  } else if (query.isError) {
    body = (
      <div className="space-y-3">
        <p className="text-danger">{t('libraryError')}</p>
        <button
          type="button"
          onClick={() => void query.refetch()}
          disabled={query.isFetching}
          className={primaryButton}
        >
          {t('tryAgain')}
        </button>
      </div>
    )
  } else if (query.data.length === 0) {
    body = <p className="text-muted">{t('libraryEmpty')}</p>
  } else {
    body = (
      <ul className="space-y-3">
        {query.data.map((source) => (
          <li key={source.id} className="space-y-2 rounded-xl border border-line bg-surface p-4">
            <h3 className="font-semibold">
              <OfficialLink url={source.url} title={source.title} openLabel={t('openDocument')} />
            </h3>
            <p className="text-sm text-muted">
              {[
                source.authority,
                source.doc_type.replace('_', ' '),
                t('passages', { n: source.passages }),
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
            <SourceFacts
              documentDate={source.document_date}
              verifiedAt={source.verified_at}
              stale={source.stale}
              scanned={source.ocr}
              verificationDue={source.verification_due}
              t={t}
            />
          </li>
        ))}
      </ul>
    )
  }

  return (
    <section aria-labelledby="library-heading" className="space-y-3">
      <h2 id="library-heading" className="text-xl font-semibold">
        {t('libraryHeading')}
      </h2>
      {body}
    </section>
  )
}
