import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { KnowledgeReport } from '@/api/admin'
import { renderAt } from '@/test/render'
import { expectNoAxeViolations, jsonResponse, stubApi } from '@/test/utils'

const URL = '/api/v1/admin/knowledge'

const row = (sector: string, status: 'populated' | 'incomplete' | 'empty', passages: number) => ({
  sector,
  status,
  schemes: sector === 'education' ? 2 : 0,
  programmes: status === 'empty' ? 0 : 5,
  budget_records: 0,
  sources: status === 'empty' ? 0 : 6,
  indexed_sources: status === 'incomplete' ? 5 : status === 'empty' ? 0 : 6,
  passages,
  stale_sources: 1,
  due_sources: 2,
  scanned_sources: 0,
  missing_sources: status === 'incomplete' ? ['ghost-doc'] : [],
})

const report: KnowledgeReport = {
  sectors: [
    row('education', 'populated', 1200),
    row('health', 'incomplete', 340),
    row('transport', 'empty', 0),
  ],
  totals: {
    registered_sources: 122,
    indexed_sources: 121,
    verified_sources: 121,
    passages: 16137,
    embedded_passages: 16137,
    last_verified_at: '2026-11-01T10:00:00+00:00',
  },
  failed_ingestion: ['ghost-doc'],
  needs_new_check: ['old-doc'],
  provider: { configured: true, model: 'gemini-test' },
  assistant: {
    questions: 4,
    outcomes: { answered: 3, fallback: 1 },
    mean_ms: 1500,
    p95_ms: 4000,
    recent_failures: [{ at: '2026-11-01T10:05:00+00:00', code: 'llm_busy' }],
  },
  evaluations: {
    knowledge: {
      at: '2026-11-01T11:00:00+00:00',
      retrieval: { cases: 100, 'source_recall@5': 0.9 },
      intent_accuracy: 0.85,
      answers: null,
    },
  },
}

afterEach(() => vi.unstubAllGlobals())

async function show(token = 'right') {
  await userEvent.type(screen.getByLabelText('Admin token'), token)
  await userEvent.click(screen.getByRole('button', { name: 'Show the report' }))
}

describe('the knowledge base health page', () => {
  it('shows each sector with its records, documents and passages, and says which are not complete', async () => {
    stubApi({ [URL]: () => jsonResponse(report) })
    renderAt('/admin')

    await show()

    const table = await screen.findByRole('table', {
      name: 'Records, documents and passages in each sector',
    })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows.map((r) => within(r).getAllByRole('cell')[0]?.textContent)).toEqual([
      'Populated',
      'Incomplete',
      'Empty',
    ])
    const health = rows[1]!
    expect(within(health).getByText('5/6')).toBeVisible()
    expect(within(health).getByText('340')).toBeVisible()
    expect(screen.getByText('121 of 122')).toBeVisible()
    expect(screen.getAllByText('16,137', { selector: 'dd' })).toHaveLength(2) // searchable, embedded
  })

  it('lists what failed to index and what is due, the provider, the failures and the benchmark', async () => {
    stubApi({ [URL]: () => jsonResponse(report) })
    renderAt('/admin')

    await show()

    await screen.findByText(/ghost-doc/)
    expect(screen.getByText(/old-doc/)).toBeVisible()
    expect(screen.getByText(/gemini-test/)).toBeVisible()
    expect(screen.getByText(/llm_busy/)).toBeVisible()
    expect(screen.getByText(/source_recall@5 0.9/)).toBeVisible()
  })

  it('sends the token as a header and nowhere else', async () => {
    const fetchMock = stubApi({ [URL]: () => jsonResponse(report) })
    const { router } = renderAt('/admin')

    await show('s3cret')

    await screen.findByRole('table')
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toBe(URL)
    expect(new Headers(init?.headers).get('X-Admin-Token')).toBe('s3cret')
    expect(router.state.location.search).toBe('')
    expect(localStorage.length).toBe(0)
  })

  it('says that a wrong token is wrong', async () => {
    stubApi({
      [URL]: () =>
        jsonResponse({ error: { code: 'admin_denied', message: 'No.' } }, { status: 401 }),
    })
    renderAt('/admin')

    await show('wrong')

    expect(await screen.findByRole('alert')).toHaveTextContent('The token is wrong.')
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('says when the page is switched off on the server', async () => {
    stubApi({
      [URL]: () => jsonResponse({ error: { code: 'not_found', message: 'No.' } }, { status: 404 }),
    })
    renderAt('/admin')

    await show()

    expect(await screen.findByRole('alert')).toHaveTextContent('switched off')
  })

  it('is not linked from the public pages', () => {
    stubApi({})
    renderAt('/')

    expect(document.querySelector('a[href="/admin"]')).toBeNull()
  })

  it('has no automatically detectable accessibility problems', async () => {
    stubApi({ [URL]: () => jsonResponse(report) })
    const { container } = renderAt('/admin')
    await show()
    await screen.findByRole('table')

    await expectNoAxeViolations(container)
  })
})
