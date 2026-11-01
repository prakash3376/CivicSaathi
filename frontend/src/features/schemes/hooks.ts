import { useMutation, useQuery } from '@tanstack/react-query'
import { checkEligibility, fetchBudget, fetchScheme, fetchSchemes } from '@/api/schemes'
import type { EligibilityRequest } from '@/api/types'

const FIVE_MINUTES_MS = 5 * 60_000

/** The catalogue. Rules change only when the documents are re-read, so it is kept a while. */
export function useSchemes() {
  return useQuery({
    queryKey: ['schemes'],
    queryFn: ({ signal }) => fetchSchemes(signal),
    staleTime: FIVE_MINUTES_MS,
  })
}

export function useScheme(id: string) {
  return useQuery({
    queryKey: ['schemes', id],
    queryFn: ({ signal }) => fetchScheme(id, signal),
    staleTime: FIVE_MINUTES_MS,
  })
}

/**
 * A check is a mutation, not a query: it is not repeated or cached, and the answers and the
 * result are kept only in memory, for as long as the page shows them.
 */
export function useEligibilityCheck(schemeId: string) {
  return useMutation({
    mutationFn: (request: EligibilityRequest) => checkEligibility(schemeId, request),
  })
}

/** What the budget documents allocate. Changes only when the documents are re-read. */
export function useBudget() {
  return useQuery({
    queryKey: ['budget'],
    queryFn: ({ signal }) => fetchBudget(signal),
    staleTime: FIVE_MINUTES_MS,
  })
}
