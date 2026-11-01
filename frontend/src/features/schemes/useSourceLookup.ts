import { useMemo } from 'react'
import { useSources } from '@/features/assistant/useSources'

export interface SourceRef {
  title: string
  url: string
}

/**
 * Titles and addresses of the official documents, by id. Empty until the list loads (or if it
 * cannot: the quotes still show, with the document's id in place of its title).
 */
export function useSourceLookup(): ReadonlyMap<string, SourceRef> {
  const { data } = useSources()
  return useMemo(
    () =>
      new Map((data ?? []).map((source) => [source.id, { title: source.title, url: source.url }])),
    [data],
  )
}
