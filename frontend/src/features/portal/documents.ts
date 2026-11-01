import type { SourceSummary } from '@/api/types'
import { searchWords } from '@/features/sectors/searchSchemes'
import type { PortalKey, Translate } from './strings'

const TYPE_KEY: Record<string, PortalKey> = {
  guidelines: 'docTypeGuidelines',
  scheme_page: 'docTypeSchemePage',
  faq: 'docTypeFaq',
  notification: 'docTypeNotification',
  circular: 'docTypeCircular',
}

/** What kind of document it is, in words ("Notification"). */
export function docTypeLabel(t: Translate, docType: string): string {
  return t(TYPE_KEY[docType] ?? 'docTypeOther')
}

/** The kinds of document that announce something new, as opposed to a standing explanation. */
const UPDATE_TYPES = new Set(['notification', 'circular', 'order', 'amendment'])

/**
 * The documents that count as updates, newest first. A document without a date goes last: the date
 * is never guessed.
 */
export function latestUpdates(sources: readonly SourceSummary[]): SourceSummary[] {
  return sources
    .filter((source) => UPDATE_TYPES.has(source.doc_type))
    .toSorted((a, b) => (b.document_date ?? '').localeCompare(a.document_date ?? ''))
}

/** Does the document match every word typed, in its title, scheme or department? */
export function documentMatches(source: SourceSummary, text: string): boolean {
  const wanted = searchWords(text)
  const hay = [source.title, source.scheme, source.authority, source.state ?? '']
    .join(' ')
    .toLocaleLowerCase()
  return wanted.every((word) => hay.includes(word))
}
