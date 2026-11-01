import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderAt } from '@/test/render'
import { schemeDetailsBody, schemesBody } from '@/test/schemeFixtures'
import { expectNoAxeViolations, jsonResponse, sourcesBody, stubApi } from '@/test/utils'

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubScheme() {
  return stubApi({
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    '/api/v1/schemes/svmcm': () => jsonResponse(schemeDetailsBody),
    '/api/v1/sources': () => jsonResponse(sourcesBody),
  })
}

async function open() {
  stubScheme()
  const view = renderAt('/schemes/svmcm')
  await screen.findByRole('heading', {
    level: 1,
    name: 'Swami Vivekananda Merit Cum Means Scholarship',
  })
  return view
}

describe('a scheme in detail', () => {
  it('shows what the first course pays, who can get it, and what to gather', async () => {
    await open()

    expect(screen.getByText('Rs 1,000 a month for 10 months.')).toBeVisible()
    const criteria = screen.getByRole('region', { name: 'Who can get it' })
    expect(within(criteria).getByText('Family income is at most Rs 2,50,000 a year')).toBeVisible()
    expect(within(criteria).getByText('Not required of Board toppers.')).toBeVisible()
    const documents = screen.getByRole('region', { name: 'Documents to gather' })
    expect(within(documents).getByText('Bank account details')).toBeVisible()
    expect(within(documents).getByText('Maybe needed')).toBeVisible() // only the uncertain one
    expect(
      within(screen.getByRole('region', { name: 'Also check' })).getByText(
        'You may hold only one scholarship at a time.',
      ),
    ).toBeVisible()
  })

  it('changes everything about the course when another course is chosen', async () => {
    await open()

    await userEvent.click(screen.getByRole('radio', { name: /Postgraduate/ }))

    expect(screen.getByText('Rs 2,000 a month for 10 months.')).toBeVisible()
    expect(screen.queryByText('Rs 1,000 a month for 10 months.')).toBeNull()
    expect(screen.getByText('At least 53% marks')).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Also check' })).toBeNull()
  })

  it('keeps the words of the document out of the way until asked, then shows them with their source', async () => {
    await open()
    const criteria = screen.getByRole('region', { name: 'Who can get it' })
    expect(within(criteria).queryByRole('blockquote')).toBeNull()
    expect(within(criteria).queryByText(/not more than Rs. 2,50,000/)).toBeNull()

    const [first] = within(criteria).getAllByRole('button', { name: 'Show the official words' })
    await userEvent.click(first!)

    expect(first).toHaveAttribute('aria-expanded', 'true')
    expect(first).toHaveTextContent('Hide the official words')
    expect(within(criteria).getByText(/not more than Rs. 2,50,000/)).toBeVisible()
    const link = await within(criteria).findByRole('link', {
      name: /SVMCM Scholarship: Guidelines/,
    })
    expect(link).toHaveAttribute('href', 'https://svmcm.wb.gov.in/readwrite/SVMCM_GUIDELINES.pdf')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('names the document by its id when the list of documents is not available', async () => {
    stubApi({
      '/api/v1/schemes': () => jsonResponse(schemesBody),
      '/api/v1/schemes/svmcm': () => jsonResponse(schemeDetailsBody),
      '/api/v1/sources': () =>
        jsonResponse({ error: { code: 'index_unavailable', message: 'x' } }, { status: 503 }),
    })
    renderAt('/schemes/svmcm')
    await screen.findByRole('heading', { level: 1 })

    const [first] = screen.getAllByRole('button', { name: 'Show the official words' })
    await userEvent.click(first!)

    expect(await screen.findAllByText('From: wb-svmcm-guidelines')).not.toHaveLength(0)
  })

  it('turns e-mail addresses and phone numbers into links, and says where to apply', async () => {
    await open()

    expect(screen.getByRole('link', { name: 'Email help@example.gov.in' })).toHaveAttribute(
      'href',
      'mailto:help@example.gov.in',
    )
    expect(screen.getByRole('link', { name: 'Call 033-2345-6789' })).toHaveAttribute(
      'href',
      'tel:03323456789',
    )
    const apply = screen.getByRole('link', { name: /svmcm.wb.gov.in/ })
    expect(apply).toHaveAttribute('href', 'https://svmcm.wb.gov.in')
    expect(apply).toHaveAttribute('target', '_blank')
  })

  it('does not make a link of an address that is not a web page', async () => {
    stubApi({
      '/api/v1/schemes': () => jsonResponse(schemesBody),
      '/api/v1/sources': () => jsonResponse(sourcesBody),
      '/api/v1/schemes/svmcm': () =>
        jsonResponse({
          ...schemeDetailsBody,
          apply: { ...schemeDetailsBody.apply, url: 'javascript:alert(document.cookie)' },
        }),
    })
    renderAt('/schemes/svmcm')
    await screen.findByRole('heading', { level: 1 })

    const apply = screen.getByRole('region', { name: 'Where to apply' })

    expect(within(apply).queryByRole('link')).toBeNull()
    expect(within(apply).getByText('javascript:alert(document.cookie)')).toBeVisible()
  })

  it('says plainly what the documents do not say, and that there is no stated last date', async () => {
    await open()

    const unsaid = screen.getByRole('region', { name: 'The documents do not say' })
    expect(within(unsaid).getByText('The last date to apply.')).toBeVisible()
    expect(within(unsaid).getByText('Any fee for applying.')).toBeVisible()
    expect(
      within(screen.getByRole('region', { name: 'Dates' })).getByText(
        'The documents give no last date.',
      ),
    ).toBeVisible()
  })

  it('leads to the check for the chosen course, and to a question about the scheme', async () => {
    await open()

    expect(screen.getByRole('link', { name: 'Check if I am eligible' })).toHaveAttribute(
      'href',
      '/schemes/svmcm/check?track=ug',
    )
    await userEvent.click(screen.getByRole('radio', { name: /Postgraduate/ }))
    expect(screen.getByRole('link', { name: 'Check if I am eligible' })).toHaveAttribute(
      'href',
      '/schemes/svmcm/check?track=pg',
    )
    expect(screen.getByRole('link', { name: 'Ask about this scheme' })).toHaveAttribute(
      'href',
      '/ask?scheme=svmcm',
    )
    expect(screen.getByRole('link', { name: 'All schemes' })).toHaveAttribute('href', '/schemes')
  })

  it('says so when there is no such scheme', async () => {
    stubApi({
      '/api/v1/schemes/ghost': () =>
        jsonResponse(
          { error: { code: 'scheme_not_found', message: 'There is no such scheme.' } },
          { status: 404 },
        ),
    })
    renderAt('/schemes/ghost')

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Scheme not found')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('offers to try again when the scheme cannot be loaded', async () => {
    stubApi({
      '/api/v1/schemes/svmcm': () =>
        jsonResponse(
          { error: { code: 'schemes_unavailable', message: 'Not available.' } },
          { status: 503 },
        ),
    })
    renderAt('/schemes/svmcm')

    expect(await screen.findByRole('alert')).toHaveTextContent('The schemes could not be loaded.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled()
  })

  it('reads in Bengali, with the official quote left in the language of the document', async () => {
    await open()

    await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))

    expect(screen.getByText('মাসে 1,000 টাকা, 10 মাস।')).toBeVisible()
    expect(screen.getByRole('region', { name: 'কারা পেতে পারে' })).toBeVisible()
    const criteria = screen.getByRole('region', { name: 'কারা পেতে পারে' })
    const [first] = within(criteria).getAllByRole('button', { name: 'সরকারি নথির ভাষা দেখুন' })
    await userEvent.click(first!)
    expect(screen.getByText(/not more than Rs. 2,50,000/).closest('blockquote')).toHaveAttribute(
      'lang',
      'en',
    )
  })

  it('has no automatically detectable accessibility problems, in English or Bengali', async () => {
    const { container } = await open()
    await userEvent.click(screen.getAllByRole('button', { name: 'Show the official words' })[0]!)
    await expectNoAxeViolations(container)

    await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))

    await expectNoAxeViolations(container)
  })
})
