import { apiFetch } from './client'
import type { Answer, AskRequest, SourceSummary, SourcesResponse } from './types'

/** Answering means searching the documents and waiting for a language model: allow it time. */
const ASK_TIMEOUT_MS = 60_000

export function askQuestion(request: AskRequest, signal?: AbortSignal): Promise<Answer> {
  return apiFetch<Answer>('/api/v1/assistant/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    cache: 'no-store', // an answer is personal to the question
    signal,
    timeoutMs: ASK_TIMEOUT_MS,
  })
}

export async function fetchSources(signal?: AbortSignal): Promise<SourceSummary[]> {
  const reply = await apiFetch<SourcesResponse>('/api/v1/sources', {
    signal,
    cache: 'no-cache', // keep a copy, but ask the server every time (it answers 304 if unchanged)
  })
  return reply.sources
}
