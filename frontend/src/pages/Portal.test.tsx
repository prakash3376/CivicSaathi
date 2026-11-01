import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { formatDate } from '@/features/assistant/dates'
import { SECTOR_IDS, SECTOR_KEY } from '@/features/sectors/sectors'
import { strings as sectorStrings } from '@/features/sectors/strings'
import { renderAt } from '@/test/render'
import { installRecognition, resetSpeaker } from '@/test/speech'
import { schemesBody } from '@/test/schemeFixtures'
import { expectNoAxeViolations, jsonResponse, sourceBody, sourcesBody, stubApi } from '@/test/utils'

const ASK = '/api/v1/assistant/ask'

const notification = {
  ...sourceBody,
  id: 'aicte-notice',
  title: 'AICTE notification for 2026-27',
  authority: 'AICTE',
  doc_type: 'notification',
  document_date: '2026-09-01',
}

function stubAll(sources = sourcesBody) {
  return stubApi({
    '/api/v1/sources': () => jsonResponse(sources),
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    '/api/v1/budget': () => jsonResponse({ records: [] }),
    [ASK]: () => jsonResponse({}),
  })
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  resetSpeaker()
  vi.unstubAllGlobals()
})

const region = (name: string) => within(screen.getByRole('region', { name }))

describe('the home page', () => {
  it('shows the twelve sectors, each leading to its own page', () => {
    stubAll()
    renderAt('/')

    const links = region('Find help by sector').getAllByRole('link')

    expect(links).toHaveLength(12)
    expect(links.map((link) => link.getAttribute('href'))).toEqual(
      SECTOR_IDS.map((id) => `/sectors/${id}`),
    )
  })

  it('counts the verified schemes of a sector, and says nothing while they load', async () => {
    stubAll()
    renderAt('/')
    const sectors = region('Find help by sector')
    expect(sectors.queryByText(/verified scheme/)).toBeNull()

    expect(await sectors.findByText('2 verified schemes')).toBeVisible()
    expect(sectors.getAllByText('Being added')).toHaveLength(11)
  })

  it('shows verified schemes from the catalogue, with both actions and no invented date', async () => {
    stubAll()
    renderAt('/')
    const featured = region('Explore important government schemes')

    const cards = await featured.findAllByRole('article')

    expect(cards).toHaveLength(2)
    expect(within(cards[0]!).getByRole('link', { name: /See details/ })).toHaveAttribute(
      'href',
      '/schemes/svmcm',
    )
    expect(within(cards[0]!).getByRole('link', { name: /Check if I am eligible/ })).toHaveAttribute(
      'href',
      '/schemes/svmcm/check',
    )
    expect(within(cards[0]!).queryByText(/Last date/)).toBeNull() // the documents give none
    expect(featured.getByRole('link', { name: 'See all schemes' })).toHaveAttribute(
      'href',
      '/schemes',
    )
  })

  it('shows announcements as updates, with who issued them and the date in the document', async () => {
    stubAll({ sources: [...sourcesBody.sources, notification] })
    renderAt('/')
    const updates = region('Latest Government Updates')

    const link = await updates.findByRole('link', { name: /AICTE notification for 2026-27/ })

    expect(link).toHaveAttribute('href', notification.url)
    expect(updates.getByText('AICTE \u{B7} Notification')).toBeVisible()
    expect(updates.getByText(new RegExp(formatDate('2026-09-01', 'en')))).toBeVisible()
    // A standing guideline is not an update.
    expect(updates.queryByText('SVMCM Scholarship: Guidelines')).toBeNull()
  })

  it('says so when no announcement has been added, rather than filling the space', async () => {
    stubAll()
    renderAt('/')

    expect(
      await region('Latest Government Updates').findByText(
        'No official updates have been added yet.',
      ),
    ).toBeVisible()
  })

  it('explains in three steps how it works', () => {
    stubAll()
    renderAt('/')

    const steps = region('How CivicSaathi works').getAllByRole('listitem')

    expect(steps.map((step) => step.textContent)).toEqual([
      '1ExploreFind government schemes or policies.',
      '2UnderstandGet AI-powered explanations in your language.',
      '3Take ActionCheck eligibility, collect documents and visit official portals.',
    ])
  })

  it('has no automatically detectable accessibility problems once loaded, in all three languages', async () => {
    stubAll({ sources: [...sourcesBody.sources, notification] })
    const { container } = renderAt('/')
    await screen.findByText('2 verified schemes')

    await expectNoAxeViolations(container)
    await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))
    await expectNoAxeViolations(container)
    await userEvent.click(screen.getByRole('button', { name: 'हिन्दी' }))
    await expectNoAxeViolations(container)
  })
})

describe('the search box', () => {
  it('searches schemes and documents for what was typed', async () => {
    stubAll()
    const { router } = renderAt('/')

    await userEvent.type(screen.getByRole('searchbox'), 'girls scholarship')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    expect(router.state.location.pathname).toBe('/search')
    expect(router.state.location.search).toBe('?q=girls%20scholarship')
  })

  it('searches when Enter is pressed, and does nothing for an empty box', async () => {
    stubAll()
    const { router } = renderAt('/')

    await userEvent.type(screen.getByRole('searchbox'), '{Enter}')
    expect(router.state.location.pathname).toBe('/')
    expect(screen.getByRole('searchbox')).toHaveFocus()

    await userEvent.type(screen.getByRole('searchbox'), 'farmers{Enter}')
    expect(router.state.location.search).toBe('?q=farmers')
  })

  it('hands a question to the assistant, typed in its box, and never sends it by itself', async () => {
    const fetchMock = stubAll()
    const { router } = renderAt('/')

    await userEvent.type(screen.getByRole('searchbox'), 'Who can apply for Pragati?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask AI Saathi' }))

    expect(router.state.location.pathname).toBe('/ask')
    expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue(
      'Who can apply for Pragati?',
    )
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === ASK)).toHaveLength(0)
  })

  it('opens the assistant empty when nothing was typed', async () => {
    stubAll()
    const { router } = renderAt('/')

    await userEvent.click(screen.getByRole('button', { name: 'Ask AI Saathi' }))

    expect(router.state.location.search).toBe('')
    expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue('')
  })

  it('fills the box from an example, to be read and changed before searching', async () => {
    stubAll()
    renderAt('/')

    await userEvent.click(
      screen.getByRole('button', { name: 'What government schemes are available for farmers?' }),
    )

    expect(screen.getByRole('searchbox')).toHaveValue(
      'What government schemes are available for farmers?',
    )
    expect(screen.getByRole('searchbox')).toHaveFocus()
  })

  it('offers the five example questions', () => {
    stubAll()
    renderAt('/')

    expect(screen.getByRole('list', { name: 'Try one of these:' }).children).toHaveLength(5)
  })

  it('says where microphone audio goes, and puts the words in the box without searching', async () => {
    stubAll()
    const recognition = installRecognition()
    const { router } = renderAt('/')
    expect(screen.getByText(/speech service|browser/i, { selector: 'p' })).toBeVisible()

    await userEvent.type(screen.getByRole('searchbox'), 'farmers')
    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))
    act(() => recognition.last()!.hear('and crop insurance'))

    expect(screen.getByRole('searchbox')).toHaveValue('farmers and crop insurance')
    expect(router.state.location.pathname).toBe('/') // nothing is sent by itself
  })

  it('says so when the browser cannot turn speech into text', () => {
    stubAll()
    renderAt('/')

    expect(screen.getByText(/cannot turn speech into text/)).toBeVisible()
  })
})

describe('the search results', () => {
  it('lists the sectors, schemes and documents that match, and offers the assistant', async () => {
    stubAll()
    renderAt('/search?q=scholarship')

    expect(screen.getByRole('heading', { name: 'Results for "scholarship"' })).toBeVisible()
    expect(
      within(screen.getByRole('main')).getByRole('link', { name: 'Ask AI Saathi' }),
    ).toHaveAttribute('href', '/ask?q=scholarship')
    expect(await screen.findByRole('heading', { name: 'Sectors' })).toBeVisible()
    expect(screen.getAllByRole('article')).toHaveLength(2)
    expect(screen.getByRole('link', { name: /Education & Scholarships/ })).toHaveAttribute(
      'href',
      '/sectors/education',
    )
    expect(screen.getByRole('heading', { name: 'Official documents' })).toBeVisible()
  })

  it('ignores punctuation, so a question mark does not hide a match', async () => {
    stubAll()
    renderAt('/search?q=girls%3F')

    const cards = await screen.findAllByRole('article')

    expect(cards).toHaveLength(1)
    expect(cards[0]).toHaveTextContent('AICTE Pragati Scholarship for Girls')
  })

  it('says that nothing matched, and where to go instead', async () => {
    stubAll()
    renderAt('/search?q=zzzz')

    expect(await screen.findByText('Nothing matched "zzzz".')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Browse the sectors' })).toHaveAttribute(
      'href',
      '/schemes',
    )
    expect(screen.queryByRole('article')).toBeNull()
  })

  it('asks for a word when there is none', () => {
    stubAll()
    renderAt('/search')

    expect(screen.getByText('Type a word or a question above to search.')).toBeVisible()
  })

  it('keeps what was searched for in the box', () => {
    stubAll()
    renderAt('/search?q=farmers')

    expect(screen.getByRole('searchbox')).toHaveValue('farmers')
  })

  it('says so, with a way to try again, when the schemes cannot be loaded', async () => {
    stubApi({
      '/api/v1/sources': () => jsonResponse(sourcesBody),
      '/api/v1/budget': () => jsonResponse({ records: [] }),
      '/api/v1/schemes': () =>
        jsonResponse(
          { error: { code: 'schemes_unavailable', message: 'No.', request_id: 'req-9' } },
          { status: 503 },
        ),
    })
    renderAt('/search?q=scholarship')

    const alert = await screen.findByRole('alert')

    expect(alert).toHaveTextContent('The search could not be completed.')
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeVisible()
  })

  it('has no automatically detectable accessibility problems', async () => {
    stubAll()
    const { container } = renderAt('/search?q=scholarship')
    await screen.findByRole('heading', { name: 'Sectors' })

    await expectNoAxeViolations(container)
  })
})

describe('the sector pages', () => {
  it.each(SECTOR_IDS)('opens %s with its name and what it covers', (id) => {
    stubAll()
    renderAt(`/sectors/${id}`)

    const key = SECTOR_KEY[id]
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      sectorStrings.en[`${key}Title`],
    )
    expect(screen.getByText(sectorStrings.en[`${key}Text`])).toBeVisible()
    expect(screen.getByRole('link', { name: 'All sectors' })).toHaveAttribute('href', '/schemes')
    expect(screen.getByRole('link', { name: 'Ask a question' })).toHaveAttribute(
      'href',
      `/ask?sector=${id}`,
    )
  })

  it('shows the scholarship schemes, their documents and questions under Education', async () => {
    stubAll()
    renderAt('/sectors/education')

    expect(await screen.findAllByRole('article')).toHaveLength(2)
    expect(screen.getByRole('link', { name: /Check if I am eligible: Swami/ })).toHaveAttribute(
      'href',
      '/schemes/svmcm/check',
    )
    expect(screen.getByRole('link', { name: /SVMCM Scholarship: Guidelines/ })).toBeVisible()
    expect(
      screen.getByRole('link', { name: 'Who can apply for the AICTE Pragati scholarship?' }),
    ).toHaveAttribute(
      'href',
      '/ask?sector=education&q=Who%20can%20apply%20for%20the%20AICTE%20Pragati%20scholarship%3F',
    )
  })

  it.each(SECTOR_IDS.filter((id) => id !== 'education'))(
    'shows %s as having no verified information yet, and invents nothing',
    async (id) => {
      stubAll()
      renderAt(`/sectors/${id}`)

      expect(
        await screen.findByText('Verified information is being added to this category.'),
      ).toBeVisible()
      expect(screen.queryByRole('article')).toBeNull()
      expect(screen.queryByRole('searchbox')).toBeNull() // nothing to search
      expect(screen.queryByText(/Last date/)).toBeNull()
    },
  )

  it('says that budget figures are not schemes', async () => {
    stubAll()
    renderAt('/sectors/budget')

    expect(await screen.findByText(/Budget figures are not schemes/)).toBeVisible()
  })

  it('shows a not-found page for a sector that does not exist', () => {
    stubAll()
    renderAt('/sectors/astrology')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Page not found')
  })

  it('narrows the schemes by Central or State, by state and by words, and says how many', async () => {
    stubAll()
    renderAt('/sectors/education')
    await screen.findAllByRole('article')
    expect(screen.getByText('Showing 2 schemes')).toBeVisible()

    await userEvent.selectOptions(screen.getByLabelText('Run by'), 'central')
    expect(screen.getByText('Showing 1 scheme')).toBeVisible()
    expect(screen.getByRole('article')).toHaveTextContent('AICTE Pragati')

    await userEvent.selectOptions(screen.getByLabelText('Run by'), 'all')
    await userEvent.selectOptions(screen.getByLabelText('State'), 'West Bengal')
    expect(screen.getByRole('article')).toHaveTextContent('Swami Vivekananda')

    await userEvent.selectOptions(screen.getByLabelText('State'), '')
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search schemes' }), 'girls diploma')
    expect(screen.getByRole('article')).toHaveTextContent('AICTE Pragati')
  })

  it('says when the filters hide every scheme, and clears them', async () => {
    stubAll()
    renderAt('/sectors/education')
    await screen.findAllByRole('article')

    await userEvent.type(screen.getByRole('searchbox', { name: 'Search schemes' }), 'zzzz')

    expect(screen.queryByRole('article')).toBeNull()
    expect(screen.getByText(/No scheme matches these filters/)).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getAllByRole('article')).toHaveLength(2)
  })

  it('says so, with a way to try again, when the schemes cannot be loaded', async () => {
    stubApi({
      '/api/v1/sources': () => jsonResponse(sourcesBody),
      '/api/v1/budget': () => jsonResponse({ records: [] }),
      '/api/v1/schemes': () =>
        jsonResponse(
          { error: { code: 'schemes_unavailable', message: 'No.', request_id: 'req-4' } },
          { status: 503 },
        ),
    })
    renderAt('/sectors/education')

    const alert = await screen.findByRole('alert')

    expect(alert).toHaveTextContent('The schemes could not be loaded.')
    expect(alert).toHaveTextContent('Reference: req-4')
  })

  it('has no automatically detectable accessibility problems, with schemes and without', async () => {
    stubAll()
    const education = renderAt('/sectors/education')
    await screen.findAllByRole('article')
    await expectNoAxeViolations(education.container)
    education.unmount()

    const health = renderAt('/sectors/health')
    await screen.findByText('Verified information is being added to this category.')
    await expectNoAxeViolations(health.container)
  })
})

describe('explore schemes', () => {
  it('shows the sectors and then every verified scheme', async () => {
    stubAll()
    renderAt('/schemes')

    expect(region('Browse by sector').getAllByRole('link')).toHaveLength(12)
    expect(await region('All verified schemes').findAllByRole('article')).toHaveLength(2)
  })
})

describe('policy and rights', () => {
  it('lists the official documents with a link to the original and to a question about them', async () => {
    stubAll()
    renderAt('/policy')

    const library = region('Official documents we have read')
    const link = await library.findByRole('link', { name: /SVMCM Scholarship: Guidelines/ })

    expect(link).toHaveAttribute('href', sourceBody.url)
    expect(
      library.getByRole('link', { name: 'Swami Vivekananda Merit Cum Means Scholarship' }),
    ).toHaveAttribute('href', '/ask?scheme=svmcm')
  })

  it('searches the documents', async () => {
    stubAll()
    renderAt('/policy')
    await screen.findByRole('link', { name: /SVMCM Scholarship: Guidelines/ })

    await userEvent.type(screen.getByRole('searchbox', { name: 'Search the documents' }), 'zzzz')

    expect(screen.getByText('No document matches. Try other words.')).toBeVisible()
  })

  it('says what is not available yet, and has no upload button that would do nothing', () => {
    stubAll()
    renderAt('/policy')

    expect(region('Not available yet').getAllByRole('listitem')).toHaveLength(2)
    expect(screen.queryByRole('button', { name: /upload/i })).toBeNull()
    expect(screen.queryByLabelText(/upload|file/i)).toBeNull()
  })

  it('says so, with a way to try again, when the documents cannot be loaded', async () => {
    stubApi({
      '/api/v1/schemes': () => jsonResponse(schemesBody),
      '/api/v1/sources': () =>
        jsonResponse(
          { error: { code: 'index_unavailable', message: 'No.', request_id: 'req-5' } },
          { status: 503 },
        ),
    })
    renderAt('/policy')

    expect(await screen.findByRole('alert')).toHaveTextContent('The documents could not be loaded.')
  })

  it('has no automatically detectable accessibility problems', async () => {
    stubAll()
    const { container } = renderAt('/policy')
    await screen.findByRole('link', { name: /SVMCM Scholarship: Guidelines/ })

    await expectNoAxeViolations(container)
  })
})

describe('my profile', () => {
  it('says that no account is needed and that nothing sensitive is kept', () => {
    stubAll()
    renderAt('/profile')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('My Profile')
    expect(screen.getByText(/You do not need an account/)).toBeVisible()
    expect(screen.getByText(/do not ask for Aadhaar, PAN or bank details/)).toBeVisible()
    expect(screen.queryByRole('button', { name: /sign in|log in|register/i })).toBeNull()
  })

  it('shows the three choices the browser keeps, and clears them', async () => {
    localStorage.setItem('civicsaathi.ui-language', 'en')
    localStorage.setItem('civicsaathi.language', 'hi')
    localStorage.setItem('civicsaathi.speech-rate', 'slow')
    stubAll()
    renderAt('/profile')
    const list = within(screen.getByText('Interface language').closest('dl')!)
    expect(list.getByText('English')).toBeVisible() // the interface
    expect(list.getByText('हिन्दी')).toBeVisible() // the answers
    expect(list.getByText('Slow')).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: 'Clear saved choices' }))

    expect(screen.getByText('Saved choices cleared.')).toBeVisible()
    expect(list.getAllByText('Not set')).toHaveLength(3)
    expect(localStorage.getItem('civicsaathi.speech-rate')).toBeNull()
    expect(localStorage.getItem('civicsaathi.language')).toBeNull()
  })

  it('has no automatically detectable accessibility problems', async () => {
    stubAll()
    const { container } = renderAt('/profile')

    await expectNoAxeViolations(container)
  })
})

describe('the menu on a phone', () => {
  it('opens and closes from a button that says which, and closes when a page is chosen', async () => {
    stubAll()
    renderAt('/')
    const button = screen.getByRole('button', { name: 'Menu' })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getAllByRole('navigation', { name: 'Main' })).toHaveLength(1)

    await userEvent.click(button)

    expect(screen.getByRole('button', { name: 'Close menu' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    const phoneNav = screen.getAllByRole('navigation', { name: 'Main' })[1]!
    await userEvent.click(within(phoneNav).getByRole('link', { name: 'My Profile' }))

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('My Profile')
    expect(screen.getByRole('button', { name: 'Menu' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getAllByRole('navigation', { name: 'Main' })).toHaveLength(1)
  })
})

describe('a question carried over from the search', () => {
  it('fills the question box and sends nothing', () => {
    const fetchMock = stubAll()
    renderAt('/ask?q=What%20is%20the%20income%20limit%3F')

    expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue(
      'What is the income limit?',
    )
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === ASK)).toHaveLength(0)
  })
})
