import { apiFetch } from './client'
import type {
  BudgetRecord,
  BudgetResponse,
  EligibilityRequest,
  EligibilityResult,
  ProgrammeDetails,
  SchemeDetails,
  SchemeSummary,
  SchemesResponse,
} from './types'

/**
 * Public lists are the same for everyone and change rarely, but a deadline's status depends on
 * today's date. `no-cache` lets the browser keep a copy and ask the server every time whether it is
 * still current (the server answers 304 with no body if it is), so a copy is never trusted blindly.
 */
const REVALIDATE: RequestCache = 'no-cache'

export async function fetchSchemes(signal?: AbortSignal): Promise<SchemeSummary[]> {
  // A deadline's status depends on today's date, so it is not cached by the browser.
  const reply = await apiFetch<SchemesResponse>('/api/v1/schemes', { signal, cache: REVALIDATE })
  return reply.schemes
}

export function fetchScheme(
  id: string,
  signal?: AbortSignal,
): Promise<SchemeDetails | ProgrammeDetails> {
  return apiFetch<SchemeDetails | ProgrammeDetails>(`/api/v1/schemes/${encodeURIComponent(id)}`, {
    signal,
    cache: REVALIDATE,
  })
}

export function checkEligibility(
  schemeId: string,
  request: EligibilityRequest,
  signal?: AbortSignal,
): Promise<EligibilityResult> {
  return apiFetch<EligibilityResult>(
    `/api/v1/schemes/${encodeURIComponent(schemeId)}/eligibility`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      cache: 'no-store', // the result describes one person
      signal,
    },
  )
}

export async function fetchBudget(signal?: AbortSignal): Promise<BudgetRecord[]> {
  const reply = await apiFetch<BudgetResponse>('/api/v1/budget', { signal, cache: REVALIDATE })
  return reply.records
}
