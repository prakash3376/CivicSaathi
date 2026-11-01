import { apiFetch } from './client'
import type { HealthResponse } from './types'

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/v1/health', { signal, cache: 'no-store' })
}
