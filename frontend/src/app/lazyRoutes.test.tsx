import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PAGES, createRoutes } from '@/app/router'
import { strings as layout } from '@/components/layout/strings'
import { renderLazilyAt } from '@/test/render'
import { schemesBody } from '@/test/schemeFixtures'
import { healthBody, jsonResponse, sourcesBody, stubApi } from '@/test/utils'

afterEach(() => vi.unstubAllGlobals())

function stubAll() {
  stubApi({
    '/api/v1/health': () => jsonResponse(healthBody),
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    '/api/v1/budget': () => jsonResponse({ records: [] }),
  })
}

describe('the pages that are loaded when they are first visited', () => {
  it('shows the home page at once: it is part of the first download', () => {
    stubAll()
    renderLazilyAt('/')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Government services')
  })

  it('loads the assistant page when it is visited, and then shows it', async () => {
    stubAll()
    renderLazilyAt('/ask')

    expect(
      await screen.findByRole('heading', { level: 1, name: /Ask about a scholarship/ }),
    ).toBeVisible()
    expect(screen.getByRole('textbox', { name: 'Your question' })).toBeVisible()
  })

  it('loads a sector page the same way', async () => {
    stubAll()
    renderLazilyAt('/sectors/education')

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      'Education & Scholarships',
    )
  })

  it('says that it is loading, and then shows the page inside the frame', async () => {
    stubAll()
    renderLazilyAt('/schemes')

    expect(screen.getByRole('status')).toHaveTextContent(layout.en.loading)
    expect(await screen.findByRole('heading', { level: 1, name: 'Explore schemes' })).toBeVisible()
    expect(screen.getByRole('banner')).toBeVisible()
  })

  it('says it in the language of the visitor', () => {
    localStorage.setItem('civicsaathi.ui-language', 'hi')
    stubAll()
    renderLazilyAt('/schemes')

    expect(screen.getByRole('status')).toHaveTextContent(layout.hi.loading)
    localStorage.clear()
  })

  it('has a loader for every page the routes name, and each loads a component', async () => {
    const needed = new Set<string>()
    createRoutes((name) => {
      needed.add(name)
      return {}
    })

    expect([...needed].sort()).toEqual(Object.keys(PAGES).sort())
    for (const load of Object.values(PAGES)) expect(typeof (await load())).toBe('function')
  })
})
