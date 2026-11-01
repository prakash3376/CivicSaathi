import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderAt } from '@/test/render'
import { schemeDetailsBody, schemesBody } from '@/test/schemeFixtures'
import { expectNoAxeViolations, healthBody, jsonResponse, sourcesBody, stubApi } from '@/test/utils'

function stubAll() {
  return stubApi({
    '/api/v1/health': () => jsonResponse(healthBody),
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    '/api/v1/schemes/svmcm': () => jsonResponse(schemeDetailsBody),
  })
}

beforeEach(() => {
  localStorage.clear()
  stubAll()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('routes', () => {
  it('renders the home page inside the shared layout', () => {
    renderAt('/')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Government services, made understandable.',
    )
    expect(screen.getByRole('link', { name: /skip to main content/i })).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toHaveTextContent(/not legal advice/i)
  })

  it('leads from the home page to the sectors, the catalogue and the assistant', async () => {
    renderAt('/')
    const main = within(screen.getByRole('main'))

    expect(main.getByRole('link', { name: /Education & Scholarships/ })).toHaveAttribute(
      'href',
      '/sectors/education',
    )
    expect(main.getByRole('link', { name: 'See all schemes' })).toHaveAttribute('href', '/schemes')
    expect(main.getByRole('button', { name: 'Ask AI Saathi' })).toBeInTheDocument()
    expect(
      await main.findByRole('link', { name: /Check if I am eligible: Swami/ }),
    ).toHaveAttribute('href', '/schemes/svmcm/check')
  })

  it('has the way to every part in the header of every page', () => {
    renderAt('/does-not-exist')

    const nav = screen.getByRole('navigation', { name: 'Main' })

    const links = {
      Home: '/',
      'Explore Schemes': '/schemes',
      'Policy & Rights': '/policy',
      'Ask AI Saathi': '/ask',
      'My Profile': '/profile',
    }
    for (const [name, href] of Object.entries(links)) {
      expect(within(nav).getByRole('link', { name })).toHaveAttribute('href', href)
    }
  })

  it('marks the part of the site the reader is in', () => {
    renderAt('/schemes/svmcm')

    expect(screen.getByRole('link', { name: 'Explore Schemes' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: 'Ask AI Saathi' })).not.toHaveAttribute('aria-current')
  })

  it('shows the catalogue at /schemes', async () => {
    renderAt('/schemes')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Explore schemes')
    expect(await screen.findAllByRole('article')).toHaveLength(2)
  })

  it('shows a scheme at /schemes/:id', async () => {
    renderAt('/schemes/svmcm')

    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Swami Vivekananda Merit Cum Means Scholarship',
      }),
    ).toBeInTheDocument()
  })

  it('shows the eligibility check at /schemes/:id/check', async () => {
    renderAt('/schemes/svmcm/check')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Check your eligibility' }),
    ).toBeInTheDocument()
  })

  it('shows the assistant at /ask, with the documents it answers from', async () => {
    renderAt('/ask')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ask about a scholarship')
    expect(await screen.findByText('SVMCM Scholarship: Guidelines')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Your question' })).toBeInTheDocument()
  })

  it('shows the system status at /status, which the footer links to', async () => {
    renderAt('/')
    expect(screen.getByRole('link', { name: 'System status' })).toHaveAttribute('href', '/status')

    renderAt('/status')

    expect(await screen.findByText('Connected')).toBeInTheDocument()
  })

  it('shows a not-found page for unknown addresses', () => {
    renderAt('/does-not-exist')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Page not found')
    expect(screen.getByRole('link', { name: 'Back to home' })).toHaveAttribute('href', '/')
  })
})

describe('the language switch', () => {
  it('is in the header, says which language is on, and changes the frame and the home page', async () => {
    renderAt('/')
    const english = screen.getByRole('button', { name: 'English' })
    const bengali = screen.getByRole('button', { name: 'বাংলা' })
    expect(screen.getByRole('group', { name: 'Language' })).toContainElement(english)
    expect(english).toHaveAttribute('aria-pressed', 'true')
    expect(bengali).toHaveAttribute('aria-pressed', 'false')

    await userEvent.click(bengali)

    expect(bengali).toHaveAttribute('aria-pressed', 'true')
    expect(english).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'সরকারি পরিষেবা, সহজ ভাষায়।',
    )
    expect(screen.getByRole('navigation', { name: 'প্রধান মেনু' })).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toHaveTextContent('আইনি পরামর্শ নয়')
    expect(screen.getByRole('link', { name: 'মূল অংশে যান' })).toBeInTheDocument()
  })

  it('keeps the language when moving to another page', async () => {
    renderAt('/')
    await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))

    await userEvent.click(screen.getByRole('link', { name: 'প্রকল্প খুঁজুন' }))

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('প্রকল্প খুঁজুন')
  })

  it('starts in Bengali for a browser set to Bengali, but a choice made wins', () => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('bn-IN')
    const first = renderAt('/')
    expect(first.container.querySelector('h1')).toHaveTextContent('সরকারি পরিষেবা')
    first.unmount()

    localStorage.setItem('civicsaathi.ui-language', 'en')
    renderAt('/')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Government services')
  })

  it('has no automatically detectable accessibility problems on the home page, in both languages', async () => {
    const { container } = renderAt('/')
    await expectNoAxeViolations(container)

    await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))

    await expectNoAxeViolations(container)
  })

  it('has a touch target of at least 48 pixels for the switch and the menu', () => {
    renderAt('/')

    const controls = [
      ...within(screen.getByRole('banner')).getAllByRole('button'),
      ...within(screen.getByRole('banner')).getAllByRole('link'),
      screen.getByRole('link', { name: 'System status' }),
    ]

    for (const control of controls) expect(control.className, control.outerHTML).toMatch(/min-h-12/)
  })
})
