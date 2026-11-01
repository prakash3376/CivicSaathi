import { apiFetch } from './client'

export interface SectorHealth {
  sector: string
  status: 'populated' | 'incomplete' | 'empty'
  schemes: number
  programmes: number
  budget_records: number
  sources: number
  indexed_sources: number
  passages: number
  stale_sources: number
  due_sources: number
  scanned_sources: number
  missing_sources: string[]
}

export interface EvaluationSummary {
  at: string | null
  retrieval: Record<string, number | null> | null
  intent_accuracy: number | null
  answers: Record<string, unknown> | null
}

/** Reply of `GET /api/v1/admin/knowledge`. */
export interface KnowledgeReport {
  sectors: SectorHealth[]
  totals: {
    registered_sources: number
    indexed_sources: number
    verified_sources: number
    passages: number
    embedded_passages: number
    last_verified_at: string | null
  }
  failed_ingestion: string[]
  needs_new_check: string[]
  provider: { configured: boolean; model: string }
  assistant: {
    questions: number
    outcomes: Record<string, number>
    mean_ms: number | null
    p95_ms: number | null
    recent_failures: { at: string; code: string }[]
  }
  evaluations: Record<string, EvaluationSummary>
}

/** The token is sent as a header, from memory; it is never put in an address or stored. */
export function fetchKnowledge(token: string, signal?: AbortSignal): Promise<KnowledgeReport> {
  return apiFetch<KnowledgeReport>('/api/v1/admin/knowledge', {
    headers: { 'X-Admin-Token': token },
    cache: 'no-store',
    signal,
  })
}
