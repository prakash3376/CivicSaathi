import { QueryClient } from '@tanstack/react-query'
import axe from 'axe-core'
import { expect, vi } from 'vitest'
import type { Answer, Citation, HealthResponse, SourceSummary, SourcesResponse } from '@/api/types'

/** A query client for tests: no retries, so a failing request surfaces immediately. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

export function jsonResponse(
  body: unknown,
  { status = 200, headers = {} }: { status?: number; headers?: Record<string, string> } = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

export const healthBody: HealthResponse = {
  status: 'ok',
  service: 'CivicSaathi API',
  version: '0.1.0',
  environment: 'development',
  timestamp: '2026-10-30T12:00:00Z',
  uptime_seconds: 125,
}

const PASSAGE =
  'MEANS JUDGING CRITERIA\n\nThe total family income for the prospective scholars will be not more than Rs. 2,50,000/-per annum. (Not applicable for Board Toppers)'
const QUOTE =
  'The total family income for the prospective scholars will be not more than Rs. 2,50,000/-per annum.'
const START = Array.from(PASSAGE.slice(0, PASSAGE.indexOf(QUOTE))).length

export const citationBody: Citation = {
  number: 1,
  source_id: 'wb-svmcm-guidelines',
  title: 'SVMCM Scholarship: Guidelines',
  authority: 'Government of West Bengal',
  url: 'https://svmcm.wb.gov.in/readwrite/SVMCM_GUIDELINES.pdf',
  page_start: 4,
  page_end: 4,
  section: 'MEANS JUDGING CRITERIA',
  clause: '',
  passage: PASSAGE,
  quote: QUOTE,
  language: 'en',
  highlights: [{ start: START, end: START + Array.from(QUOTE).length }],
  document_date: '2026-04-28',
  date_source: 'pdf-metadata',
  verified_at: '2026-10-31T09:00:00+00:00',
  verification: 'verified',
  age_days: 186,
  stale: false,
  ocr: false,
}

export const answerBody: Answer = {
  answerable: true,
  language: 'en',
  text: "Your family's yearly income must not be more than Rs 2,50,000.",
  claims: [
    { text: "Your family's yearly income must not be more than Rs 2,50,000.", citations: [1] },
  ],
  citations: [citationBody],
  not_stated: [],
  warnings: [],
  disclaimer: 'Informational summary, not legal advice. Check the official document before acting.',
  model: 'gemini-test',
}

export const notCoveredBody: Answer = {
  answerable: false,
  language: 'en',
  text: 'The official documents I have do not say this, so I cannot answer it. Please check the official website or helpline of the scheme.',
  claims: [],
  citations: [],
  not_stated: [],
  warnings: [],
  disclaimer: answerBody.disclaimer,
  model: null,
}

/** General help for a question the documents do not cover: no citations, labelled as such. */
export const guidanceBody: Answer = {
  answerable: false,
  guidance: true,
  guidance_intro:
    'I could not find this in the official documents I have, so here is some general help instead. It is not from an official document, so please confirm it with the local office or the helpline.',
  language: 'en',
  text: 'Most pension matters are handled by the block or district office. Keep your identity proof and your bank passbook ready.',
  follow_up: 'Which state do you live in?',
  claims: [],
  citations: [],
  not_stated: [],
  warnings: [],
  disclaimer: answerBody.disclaimer,
  model: 'gemini-test',
}

export const sourceBody: SourceSummary = {
  id: 'wb-svmcm-guidelines',
  title: 'SVMCM Scholarship: Guidelines',
  scheme: 'Swami Vivekananda Merit Cum Means Scholarship',
  authority: 'Government of West Bengal',
  level: 'state',
  state: 'West Bengal',
  doc_type: 'guidelines',
  format: 'pdf',
  url: 'https://svmcm.wb.gov.in/readwrite/SVMCM_GUIDELINES.pdf',
  passages: 21,
  document_date: '2026-04-28',
  date_source: 'pdf-metadata',
  verified_at: '2026-10-31T09:00:00+00:00',
  verification: 'verified',
  age_days: 186,
  stale: false,
  verification_due: false,
  ocr: false,
}

export const sourcesBody: SourcesResponse = {
  sources: [
    sourceBody,
    {
      ...sourceBody,
      id: 'aicte-pragati-notification-2026-27',
      title: 'AICTE Pragati: Notification 2026-27',
      authority: 'AICTE',
      doc_type: 'scheme_page',
      passages: 9,
      document_date: '2024-02-01',
      stale: true,
      ocr: true,
      verification: 'verified_with_warnings',
      verification_due: true,
    },
  ],
}

interface Call {
  method: string
  body: unknown
}
type Handler = (call: Call) => Response | Promise<Response>

/** Answer `fetch` by path. An unknown path is a 404. Returns the mock, to inspect the calls. */
export function stubApi(routes: Record<string, Handler>) {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const { pathname } = new URL(String(input), 'http://localhost')
    const handler = routes[pathname]
    if (!handler) {
      return jsonResponse({ error: { code: 'not_found', message: 'Not Found' } }, { status: 404 })
    }
    const body: unknown = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    return handler({ method: init?.method ?? 'GET', body })
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

/**
 * Fail the test if axe finds an accessibility problem in `container`. Colour contrast cannot be
 * computed in jsdom, so it is checked by measurement instead (see the tokens in index.css), and
 * "region" is off because a component under test has no page around it.
 */
export async function expectNoAxeViolations(container: Element): Promise<void> {
  const results = await axe.run(container, {
    rules: { 'color-contrast': { enabled: false }, region: { enabled: false } },
  })
  expect(
    results.violations.map(
      (violation) => `${violation.id}: ${violation.help} ${violation.nodes.map((n) => n.html)}`,
    ),
  ).toEqual([])
}
