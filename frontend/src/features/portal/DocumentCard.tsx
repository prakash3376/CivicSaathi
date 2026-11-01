import { useMemo } from 'react'
import { Link } from 'react-router'
import type { SourceSummary } from '@/api/types'
import { OfficialLink } from '@/features/assistant/OfficialLink'
import { SourceFacts } from '@/features/assistant/SourceFacts'
import { translator as assistantTranslator } from '@/features/assistant/strings'
import { docTypeLabel } from './documents'
import type { Translate } from './strings'

interface Props {
  source: SourceSummary
  t: Translate
  /** The scheme this document belongs to, to offer a question limited to it. */
  askScheme?: { id: string; label: string }
}

/**
 * An official document: its title as a link to the original, who issued it, what kind it is, its
 * date and when it was last checked. Dates are only the ones the document carries.
 */
export function DocumentCard({ source, t, askScheme }: Props) {
  const words = useMemo(() => assistantTranslator(t.language), [t.language])
  return (
    <li className="space-y-2 rounded-xl border border-line bg-surface p-4">
      <h3 className="font-semibold">
        <OfficialLink
          url={source.url}
          title={source.title}
          openLabel={words('openDocument')}
          className="inline-flex min-h-12 items-center"
        />
      </h3>
      <p className="text-sm text-muted">
        {[source.authority, docTypeLabel(t, source.doc_type)].filter(Boolean).join(' \u{B7} ')}
      </p>
      <SourceFacts
        documentDate={source.document_date}
        verifiedAt={source.verified_at}
        stale={source.stale}
        scanned={source.ocr}
        verificationDue={source.verification_due}
        t={words}
      />
      {askScheme && (
        <Link
          to={`/ask?scheme=${encodeURIComponent(askScheme.id)}`}
          className="inline-flex min-h-12 items-center text-brand underline"
        >
          {askScheme.label}
        </Link>
      )}
    </li>
  )
}
