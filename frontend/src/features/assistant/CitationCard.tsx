import type { Ref } from 'react'
import type { Citation } from '@/api/types'
import { splitByHighlights } from './highlight'
import { OfficialLink } from './OfficialLink'
import { SourceFacts } from './SourceFacts'
import type { Translate } from './strings'

interface Props {
  citation: Citation
  t: Translate
  /** Whether the original text of the passage is showing. */
  expanded: boolean
  onToggle: () => void
  /** Lets the answer move keyboard focus here when a claim's source button is pressed. */
  cardRef: Ref<HTMLLIElement>
}

function location(citation: Citation, t: Translate): string {
  const { page_start, page_end, section, clause } = citation
  const pages =
    page_start === null
      ? t('webPage')
      : page_end !== null && page_end !== page_start
        ? t('pages', { from: page_start, to: page_end })
        : t('page', { n: page_start })
  return [pages, section, clause && t('clause', { c: clause })].filter(Boolean).join(' · ')
}

/** One quote from an official document, with where it is and, on request, the passage around it. */
export function CitationCard({ citation, t, expanded, onToggle, cardRef }: Props) {
  const id = `source-${citation.number}`
  const language = citation.language ?? undefined

  return (
    // tabIndex lets a claim's source button move focus here.
    <li
      id={id}
      ref={cardRef}
      tabIndex={-1}
      className="space-y-3 rounded-xl border border-line bg-surface p-4"
    >
      <h4 className="font-semibold">
        {t('source', { n: citation.number })}:{' '}
        <OfficialLink url={citation.url} title={citation.title} openLabel={t('openDocument')} />
      </h4>
      <p className="text-sm text-muted">{location(citation, t)}</p>
      <SourceFacts
        documentDate={citation.document_date}
        verifiedAt={citation.verified_at}
        stale={citation.stale}
        scanned={citation.ocr}
        t={t}
      />
      <blockquote lang={language} className="border-l-4 border-brand pl-3">
        {citation.quote}
      </blockquote>
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={`${id}-text`}
        onClick={onToggle}
        className="inline-flex min-h-12 items-center rounded-xl border border-muted px-4 font-medium hover:bg-canvas"
      >
        {expanded ? t('hideText') : t('showText')}
      </button>
      <div
        id={`${id}-text`}
        lang={language}
        hidden={!expanded}
        className="rounded-xl bg-canvas p-3 text-sm whitespace-pre-wrap"
      >
        {splitByHighlights(citation.passage, citation.highlights).map(({ text, marked }, index) =>
          marked ? (
            <mark key={index} className="bg-mark text-ink">
              {text}
            </mark>
          ) : (
            <span key={index}>{text}</span>
          ),
        )}
      </div>
    </li>
  )
}
