import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { schemesBody } from '@/test/schemeFixtures'
import { renderAt } from '@/test/render'
import { expectNoAxeViolations, jsonResponse, sourcesBody, stubApi } from '@/test/utils'

const SCHEMES = '/api/v1/schemes'

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubCatalogue() {
  return stubApi({
    [SCHEMES]: () => jsonResponse(schemesBody),
    '/api/v1/sources': () => jsonResponse(sourcesBody),
  })
}

describe('the catalogue', () => {
  it('lists every scheme with who runs it, what it is for, and its courses', async () => {
    stubCatalogue()
    renderAt('/schemes')

    const cards = await screen.findAllByRole('article')

    expect(cards).toHaveLength(2)
    const svmcm = within(cards[0]!)
    expect(svmcm.getByRole('heading', { level: 2 })).toHaveTextContent(
      'Swami Vivekananda Merit Cum Means Scholarship',
    )
    expect(
      svmcm.getByText(/Government of West Bengal · State government: West Bengal/),
    ).toBeVisible()
    expect(svmcm.getByText('A yearly scholarship for students of West Bengal.')).toBeVisible()
    expect(svmcm.getByText('Undergraduate')).toBeVisible()
    expect(svmcm.getByText('Postgraduate')).toBeVisible()
    const pragati = within(cards[1]!)
    expect(pragati.getByText(/AICTE · Central government/)).toBeVisible()
  })

  it('says when a scheme closes, in words, and warns when the date is from a scan', async () => {
    stubCatalogue()
    renderAt('/schemes')

    const pragati = within((await screen.findAllByRole('article'))[1]!)

    expect(pragati.getByText('Last date to apply: 31 Oct 2026 (11 days left)')).toBeVisible()
    expect(pragati.getByText(/read from a scan: check it on the official site/)).toBeVisible()
    expect(within((await screen.findAllByRole('article'))[0]!).queryByText(/Last date/)).toBeNull()
  })

  it('leads to the details and to the check, naming the scheme for a screen reader', async () => {
    stubCatalogue()
    renderAt('/schemes')

    const details = await screen.findByRole('link', {
      name: /See details: Swami Vivekananda Merit Cum Means Scholarship/,
    })
    const check = screen.getByRole('link', {
      name: /Check if I am eligible: Swami Vivekananda Merit Cum Means Scholarship/,
    })

    expect(details).toHaveAttribute('href', '/schemes/svmcm')
    expect(check).toHaveAttribute('href', '/schemes/svmcm/check')
  })

  it('shows the wait, then says so when the schemes cannot be loaded, and tries again', async () => {
    const schemes = vi
      .fn()
      .mockImplementationOnce(() =>
        jsonResponse(
          {
            error: { code: 'schemes_unavailable', message: 'Not available.', request_id: 'req-3' },
          },
          { status: 503 },
        ),
      )
      .mockImplementation(() => jsonResponse(schemesBody))
    const fetchMock = stubApi({
      [SCHEMES]: schemes,
      '/api/v1/sources': () => jsonResponse(sourcesBody),
    })
    renderAt('/schemes')

    expect(screen.getByRole('status')).toHaveTextContent('Loading…')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The schemes could not be loaded.')
    expect(alert).toHaveTextContent('Reference: req-3')
    await waitFor(() => expect(alert).toHaveFocus())

    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(await screen.findAllByRole('article')).toHaveLength(2)
    expect(fetchMock.mock.calls.filter(([url]) => url === SCHEMES)).toHaveLength(2)
  })

  it('switches to Bengali, including what the schemes say, and marks the page as Bengali', async () => {
    stubCatalogue()
    renderAt('/schemes')
    await screen.findAllByRole('article')

    await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('প্রকল্প খুঁজুন')
    expect(screen.getByText('পশ্চিমবঙ্গের শিক্ষার্থীদের জন্য বার্ষিক বৃত্তি।')).toBeVisible()
    expect(screen.getByText('আবেদনের শেষ তারিখ: 31 অক্টোবর, 2026 (আর 11 দিন)')).toBeVisible()
    expect(document.documentElement.lang).toBe('bn')
    expect(localStorage.getItem('civicsaathi.ui-language')).toBe('bn')
  })

  it('has no automatically detectable accessibility problems, in English or Bengali', async () => {
    stubCatalogue()
    const { container } = renderAt('/schemes')
    await screen.findAllByRole('article')
    await expectNoAxeViolations(container)

    await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))

    await expectNoAxeViolations(container)
  })
})
