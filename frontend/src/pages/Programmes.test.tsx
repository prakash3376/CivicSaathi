import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SECTOR_IDS } from '@/features/sectors/sectors'
import { strings as sectorStrings } from '@/features/sectors/strings'
import { budgetOf, featuredSchemes, inSector, sourceIdsOf } from '@/features/sectors/sectorSources'
import { sectorQuestions } from '@/features/sectors/questions'
import { renderAt } from '@/test/render'
import {
  budgetBody,
  catalogueBody,
  closedScheme,
  educationBudget,
  healthBudget,
  healthCover,
  healthCoverDetails,
  roadWorks,
} from '@/test/programmeFixtures'
import { expectNoAxeViolations, jsonResponse, sourcesBody, stubApi } from '@/test/utils'

const ASK = '/api/v1/assistant/ask'

function stubAll() {
  return stubApi({
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    '/api/v1/schemes': () => jsonResponse(catalogueBody),
    '/api/v1/schemes/demo-health-cover': () => jsonResponse(healthCoverDetails),
    '/api/v1/budget': () => jsonResponse(budgetBody),
    [ASK]: () => jsonResponse({}),
  })
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.unstubAllGlobals())

describe('programme cards in a sector', () => {
  it('shows who it is for and its first verified benefit, and no eligibility check', async () => {
    stubAll()
    renderAt('/sectors/health')

    const card = (
      await within(
        await screen.findByRole('region', { name: 'Schemes in this sector' }),
      ).findAllByRole('article')
    )[0]!

    expect(within(card).getByRole('heading', { name: 'Demo Health Cover' })).toBeVisible()
    expect(within(card).getByText('Scheme')).toBeVisible()
    expect(within(card).getByText('Families of the State.')).toBeVisible()
    expect(within(card).getByText('Cover of Rs. 5,00,000 per family per year.')).toBeVisible()
    expect(within(card).getByRole('link', { name: /See details/ })).toHaveAttribute(
      'href',
      '/schemes/demo-health-cover',
    )
    expect(within(card).queryByRole('link', { name: /Check if I am eligible/ })).toBeNull()
  })

  it('lists a programme under each of its sectors, once in each', async () => {
    stubAll()
    const schemes = () => within(screen.getByRole('region', { name: 'Schemes in this sector' }))
    const health = renderAt('/sectors/health')
    await screen.findByRole('heading', { name: 'Demo Health Cover' })
    expect(schemes().getAllByRole('article')).toHaveLength(1)
    health.unmount()

    renderAt('/sectors/social-welfare')
    await screen.findByRole('heading', { name: 'Demo Health Cover' })
    const cards = schemes().getAllByRole('article')

    expect(cards).toHaveLength(1)
    expect(cards[0]).toHaveTextContent('Demo Health Cover')
  })

  it('says what kind of programme it is, and that a public works programme pays no one', async () => {
    stubAll()
    renderAt('/sectors/transport')

    const card = (await screen.findAllByRole('article'))[0]!

    expect(within(card).getByText('Public works programme')).toBeVisible()
  })

  it('says in words that a programme is closed', async () => {
    stubAll()
    renderAt('/sectors/employment')

    expect(await screen.findByText('Closed')).toBeVisible()
  })

  it('keeps the check button for a scheme that has one', async () => {
    stubAll()
    renderAt('/sectors/education')

    expect(await screen.findAllByRole('link', { name: /Check if I am eligible/ })).toHaveLength(2)
  })

  it('counts what each sector holds on the home page', async () => {
    stubAll()
    renderAt('/')
    const sectors = within(screen.getByRole('region', { name: 'Find help by sector' }))

    // Schemes and budget records are counted apart, in words.
    expect(await sectors.findByText('2 verified schemes \u{B7} 1 budget record')).toBeVisible()
    expect(sectors.getByText('1 verified scheme \u{B7} 1 budget record')).toBeVisible() // health
    expect(sectors.getAllByText('1 verified scheme')).toHaveLength(3) // social, transport, employment
    expect(sectors.getByText('3 budget records')).toBeVisible() // the Budget sector holds them all
    expect(sectors.getAllByText('Being added')).toHaveLength(6)
  })

  it('features schemes from different sectors on the home page', async () => {
    stubAll()
    renderAt('/')
    const featured = within(
      screen.getByRole('region', { name: 'Explore important government schemes' }),
    )

    const cards = await featured.findAllByRole('article')

    // One from each sector in turn: education, health, employment (closed is skipped), transport...
    const names = cards.map((card) => within(card).getByRole('heading').textContent)
    expect(names.slice(0, 3)).toEqual([
      'Swami Vivekananda Merit Cum Means Scholarship',
      'Demo Health Cover',
      'Demo Rural Roads',
    ])
    expect(names).not.toContain('Demo Closed Scheme')
  })

  it('finds a programme from the search, by its benefit words in the summary', async () => {
    stubAll()
    renderAt('/search?q=hospital')

    expect(await screen.findByRole('heading', { name: 'Demo Health Cover' })).toBeVisible()
  })
})

describe('a programme in full', () => {
  it('shows what it gives, who can get it, who cannot, what to bring and how to apply', async () => {
    stubAll()
    renderAt('/schemes/demo-health-cover')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Demo Health Cover' }),
    ).toBeVisible()
    const heading = (name: string) => screen.getByRole('heading', { level: 2, name })
    expect(heading('What you get')).toBeVisible()
    expect(
      screen.getByText('Cover of Rs. 5,00,000 per family per year.', { selector: 'p' }),
    ).toBeVisible()
    expect(heading('Who can get it')).toBeVisible()
    expect(screen.getByText('Any family living in the State may enrol.')).toBeVisible()
    expect(heading('Who cannot get it')).toBeVisible()
    expect(screen.getByText('Serving government employees are not covered.')).toBeVisible()
    expect(heading('What to bring')).toBeVisible()
    expect(screen.getByText('A ration card.')).toBeVisible()
    expect(heading('How to apply')).toBeVisible()
    expect(screen.getByText('Visit the nearest enrolment camp.')).toBeVisible()
    expect(screen.getByText('The last date to enrol.')).toBeVisible() // what the documents do not say
    expect(screen.getByText(/Checked against official documents on/)).toBeVisible()
    expect(screen.getByText('Applies in: West Bengal')).toBeVisible()
  })

  it('opens the official portal in a new tab, safely', async () => {
    stubAll()
    renderAt('/schemes/demo-health-cover')

    const portal = await screen.findByRole('link', { name: /Open the official portal/ })

    expect(portal).toHaveAttribute('href', 'https://health.demo.gov.in')
    expect(portal).toHaveAttribute('target', '_blank')
    expect(portal).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('shows the official words behind a statement, and where they are, on request', async () => {
    stubAll()
    renderAt('/schemes/demo-health-cover')
    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByText('Each family is covered up to Rs. 5,00,000 per year.')).toBeNull()

    await userEvent.click(screen.getAllByRole('button', { name: 'Show the official words' })[0]!)

    expect(screen.getByText('Each family is covered up to Rs. 5,00,000 per year.')).toBeVisible()
    expect(screen.getByText(/page 3/)).toBeVisible()
  })

  it('has no eligibility check, and its check address says so and leads back', async () => {
    stubAll()
    renderAt('/schemes/demo-health-cover/check')

    expect(
      await screen.findByRole('heading', { name: 'There is no eligibility check for this one' }),
    ).toBeVisible()
    expect(screen.getByRole('link', { name: 'See details' })).toHaveAttribute(
      'href',
      '/schemes/demo-health-cover',
    )
    expect(screen.queryByRole('button', { name: 'Check' })).toBeNull()
  })

  it('tells a Bengali reader that the details are in English, as in the documents', async () => {
    localStorage.setItem('civicsaathi.ui-language', 'bn')
    stubAll()
    renderAt('/schemes/demo-health-cover')

    expect(await screen.findByText(/ইংরেজিতে, সরকারি নথিতে যেমন আছে/)).toBeVisible()
    expect(screen.getByText('Any family living in the State may enrol.')).toHaveAttribute(
      'lang',
      'en',
    )
  })

  it('has no automatically detectable accessibility problems', async () => {
    stubAll()
    const { container } = renderAt('/schemes/demo-health-cover')
    await screen.findByRole('heading', { level: 1 })

    await expectNoAxeViolations(container)
  })
})

describe('the budget', () => {
  it('shows each record with its year and the kind of every figure, and the words behind it', async () => {
    stubAll()
    renderAt('/sectors/budget')
    expect(
      await screen.findByRole('heading', { name: 'What the budget documents say' }),
    ).toBeVisible()

    const articles = await screen.findAllByRole('article')

    expect(articles).toHaveLength(3)
    const education = articles.find((a) => a.textContent?.includes('Education'))!
    expect(within(education).getByText('Budget 2026-27')).toBeVisible()
    expect(within(education).getByText('West Bengal Budget 2026-27: Education')).toBeVisible()
    expect(within(education).getByText(/State budget: West Bengal/)).toBeVisible()
    // Three figures of three kinds, each with its own year, never mixed.
    expect(within(education).getByText(/Budget Estimate/)).toBeVisible()
    expect(within(education).getByText(/Revised Estimate/)).toBeVisible()
    expect(within(education).getByText(/Actual spending/)).toBeVisible()
    expect(within(education).getByText('\u{20B9}41,000 crore')).toBeVisible()
    expect(within(education).getByText('\u{20B9}37,500 crore')).toBeVisible()
  })

  it('writes amounts with Indian digit grouping and the digits 0-9', async () => {
    localStorage.setItem('civicsaathi.ui-language', 'hi')
    stubAll()
    renderAt('/sectors/budget')

    expect(await screen.findByText(`\u{20B9}1,28,650 ${sectorStrings.hi.unitCrore}`)).toBeVisible()
  })

  it('says that an estimate is a plan and not money already spent, but not when there is an actual', async () => {
    stubAll()
    renderAt('/sectors/budget')
    const articles = await screen.findAllByRole('article')
    const health = articles.find((a) => a.textContent?.includes('Health'))!
    const education = articles.find((a) => a.textContent?.includes('Education'))!

    expect(within(health).getByText(/not money already spent/)).toBeVisible()
    expect(within(education).queryByText(/not money already spent/)).toBeNull()
  })

  it('shows tax announcements as statements with their words', async () => {
    stubAll()
    renderAt('/sectors/budget')
    const tax = (await screen.findAllByRole('article')).find((a) =>
      a.textContent?.includes('Taxation'),
    )!

    expect(within(tax).getByText('The tax slabs are changed.')).toBeVisible()
    expect(within(tax).getByText('Tax')).toBeVisible()
    expect(within(tax).queryByText('Figures')).toBeNull()
  })

  it('puts a sector’s own allocations on its page, and only those', async () => {
    stubAll()
    renderAt('/sectors/education')

    const section = within(await screen.findByRole('region', { name: /Budget records for/ }))

    expect(section.getByText('West Bengal Budget 2026-27: Education')).toBeVisible()
    expect(section.queryByText('Union Budget 2026-27: Health')).toBeNull()
  })

  it('says so, with a way to try again, when the budget cannot be loaded', async () => {
    stubApi({
      '/api/v1/sources': () => jsonResponse(sourcesBody),
      '/api/v1/schemes': () => jsonResponse(catalogueBody),
      '/api/v1/budget': () =>
        jsonResponse(
          { error: { code: 'schemes_unavailable', message: 'No.', request_id: 'req-8' } },
          { status: 503 },
        ),
    })
    renderAt('/sectors/budget')

    const alert = await screen.findByRole('alert')

    expect(alert).toHaveTextContent('The budget records could not be loaded.')
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeVisible()
  })

  it('has no automatically detectable accessibility problems', async () => {
    stubAll()
    const { container } = renderAt('/sectors/budget')
    await screen.findByRole('heading', { name: 'What the budget documents say' })

    await expectNoAxeViolations(container)
  })
})

describe('asking about a sector', () => {
  it('nudges the search towards the sector and says so, without limiting it', async () => {
    const fetchMock = stubAll()
    renderAt('/ask?sector=health')
    expect(
      await screen.findByText(/Looking first at the official documents about Healthcare/),
    ).toBeVisible()

    await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), 'Who is covered?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    const call = fetchMock.mock.calls.find(([url]) => String(url) === ASK)!
    const body = JSON.parse(String(call[1]?.body)) as Record<string, unknown>
    expect(body.sector).toBe('health')
    expect(body).not.toHaveProperty('source_ids') // a hint, never a hard limit
  })

  it('can be widened to everything again', async () => {
    const fetchMock = stubAll()
    renderAt('/ask?sector=health')
    await userEvent.click(await screen.findByRole('button', { name: 'Ask about everything' }))

    expect(screen.queryByText(/Looking first at the official documents about/)).toBeNull()
    await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), 'Anything?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    const call = fetchMock.mock.calls.find(([url]) => String(url) === ASK)!
    const body = JSON.parse(String(call[1]?.body)) as Record<string, unknown>
    expect(body).not.toHaveProperty('sector')
    expect(body).not.toHaveProperty('source_ids')
  })

  it('still limits the answer to one scheme when a scheme was chosen', async () => {
    const fetchMock = stubAll()
    renderAt('/ask?scheme=demo-health-cover')
    await screen.findByText(/Answers will come only from the documents of/)

    await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), 'Who is covered?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    const call = fetchMock.mock.calls.find(([url]) => String(url) === ASK)!
    expect(JSON.parse(String(call[1]?.body))).toMatchObject({ source_ids: ['demo-health-guide'] })
  })

  it('offers a question of its own in every sector, from the sector page', async () => {
    stubAll()
    renderAt('/sectors/health')

    const link = await screen.findByRole('link', {
      name: 'What government health insurance is available in West Bengal?',
    })

    expect(link).toHaveAttribute(
      'href',
      '/ask?sector=health&q=What%20government%20health%20insurance%20is%20available%20in%20West%20Bengal%3F',
    )
  })
})

describe('sector helpers', () => {
  const all = catalogueBody.schemes

  it('lists a programme under every sector it names', () => {
    expect(inSector(all, 'health')).toEqual([healthCover])
    expect(inSector(all, 'social-welfare')).toEqual([healthCover])
    expect(inSector(all, 'transport')).toEqual([roadWorks])
    expect(inSector(all, 'housing')).toEqual([])
  })

  it('gives a sector its own budget records, and the Budget sector all of them', () => {
    const records = budgetBody.records
    expect(budgetOf(records, 'health')).toEqual([healthBudget])
    expect(budgetOf(records, 'education')).toEqual([educationBudget])
    expect(budgetOf(records, 'budget')).toHaveLength(3)
  })

  it('scopes a question to the documents behind a sector, with no repeats', () => {
    expect(sourceIdsOf('health', all, budgetBody.records).sort()).toEqual([
      'demo-budget-doc',
      'demo-health-guide',
    ])
    expect(sourceIdsOf('housing', all, budgetBody.records)).toEqual([])
  })

  it('features round by round and skips what is not running', () => {
    expect(featuredSchemes(all, 3).map((s) => s.id)).toEqual([
      'svmcm',
      'demo-health-cover',
      'demo-roads',
    ])
    expect(featuredSchemes(all, 20).map((s) => s.id)).not.toContain(closedScheme.id)
    expect(featuredSchemes([], 3)).toEqual([])
  })

  it('has a question to offer in every sector and every language', () => {
    for (const id of SECTOR_IDS) {
      for (const language of ['en', 'bn', 'hi'] as const) {
        expect(sectorQuestions(id, language).length, `${id} ${language}`).toBeGreaterThan(0)
      }
    }
  })
})
