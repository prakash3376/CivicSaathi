import { useQuery } from '@tanstack/react-query'
import { fetchSources } from '@/api/assistant'

const FIVE_MINUTES_MS = 5 * 60_000

/** The documents the assistant answers from. They change only when someone runs an ingest. */
export function useSources() {
  return useQuery({
    queryKey: ['sources'],
    queryFn: ({ signal }) => fetchSources(signal),
    staleTime: FIVE_MINUTES_MS,
  })
}
