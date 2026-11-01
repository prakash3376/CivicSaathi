import type { SchemeSummary } from '@/api/types'
import { local, type UiLanguage } from '@/i18n/translator'

export type LevelFilter = 'all' | 'central' | 'state'

export interface SchemeFilters {
  text: string
  level: LevelFilter
  /** A state's name, or '' for every state. */
  state: string
}

export const NO_FILTERS: SchemeFilters = { text: '', level: 'all', state: '' }

/** The words typed, lower-cased and without punctuation, so that "for farmers?" finds "farmers". */
export const searchWords = (text: string) =>
  text
    .toLocaleLowerCase()
    .replace(/[\p{P}\p{S}]+/gu, ' ')
    .split(/\s+/)
    .filter(Boolean)

/** Everything a person might type to find a scheme, in the language of the page. */
function haystack(scheme: SchemeSummary, language: UiLanguage): string {
  return [
    scheme.name,
    scheme.authority,
    scheme.state ?? '',
    local(scheme.summary, language),
    // Who it is for and what it gives are what a person types ("insurance", "farmers", "loan").
    scheme.target ? local(scheme.target, language) : '',
    scheme.benefit ?? '',
    ...scheme.tracks.map((track) => local(track.label, language)),
  ]
    .join(' ')
    .toLocaleLowerCase()
}

/** Does the scheme contain every word typed? (Words, in any order: "girls diploma".) */
export function matchesText(scheme: SchemeSummary, text: string, language: UiLanguage): boolean {
  const wanted = searchWords(text)
  if (wanted.length === 0) return true
  const text_ = haystack(scheme, language)
  return wanted.every((word) => text_.includes(word))
}

/** The schemes that pass the search words, the level and the state. */
export function filterSchemes(
  schemes: readonly SchemeSummary[],
  filters: SchemeFilters,
  language: UiLanguage,
): SchemeSummary[] {
  return schemes.filter(
    (scheme) =>
      (filters.level === 'all' || scheme.level === filters.level) &&
      (filters.state === '' || scheme.state === filters.state) &&
      matchesText(scheme, filters.text, language),
  )
}

/** The states that have a scheme, sorted, for the state filter. */
export function statesOf(schemes: readonly SchemeSummary[]): string[] {
  return [...new Set(schemes.flatMap((scheme) => (scheme.state ? [scheme.state] : [])))].sort()
}
