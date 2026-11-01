import { Link } from 'react-router'
import type { Answer } from '@/api/types'
import { primaryButton, secondaryButton } from '@/components/ui/buttonStyles'
import { useSchemes } from '@/features/schemes/hooks'
import { useSchemeText } from '@/features/schemes/useSchemeText'
import type { Translate } from './strings'

const MOST = 3

/**
 * The schemes whose documents an answer rests on, with the way on: the scheme's page and, where
 * it has one, the eligibility check. It is worked out from the citations, so it never names a
 * scheme the answer did not use.
 */
export function RelatedSchemes({ answer, t }: { answer: Answer; t: Translate }) {
  const { t: schemeT } = useSchemeText()
  const query = useSchemes()
  const cited = new Set(answer.citations.map((citation) => citation.source_id))
  const related = (query.data ?? [])
    .filter((scheme) => scheme.source_ids.some((id) => cited.has(id)))
    .slice(0, MOST)
  if (related.length === 0) return null

  return (
    // A plain block, not a region: a conversation has one of these per answer.
    <div className="space-y-3">
      <h3 className="text-lg font-semibold">{t('relatedHeading')}</h3>
      <ul className="space-y-3">
        {related.map((scheme) => (
          <li
            key={scheme.id}
            className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-4"
          >
            <span className="min-w-0 flex-1 font-medium">{scheme.name}</span>
            <Link to={`/schemes/${scheme.id}`} className={primaryButton}>
              {schemeT('viewScheme')}
              <span className="sr-only">: {scheme.name}</span>
            </Link>
            {scheme.layout === 'check' && (
              <Link to={`/schemes/${scheme.id}/check`} className={secondaryButton}>
                {schemeT('checkEligibility')}
                <span className="sr-only">: {scheme.name}</span>
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
