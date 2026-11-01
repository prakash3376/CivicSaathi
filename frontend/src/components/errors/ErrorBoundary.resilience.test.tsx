import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import { LanguageProvider } from '@/i18n/LanguageProvider'
import { renderWithPages } from '@/test/render'
import { expectNoAxeViolations } from '@/test/utils'
import { ErrorBoundary } from './ErrorBoundary'
import { ErrorPanel } from './ErrorPanel'
import { isChunkLoadError } from './isChunkLoadError'
import { reloadPage } from './reload'
import { SectionBoundary } from './SectionBoundary'

vi.mock('./reload', () => ({ reloadPage: vi.fn() }))

const INTERNAL = 'secret internal detail at /src/features/schemes/Thing.tsx:42'

/** Throws while `broken.now` is true, and renders text otherwise: a part of a page with a bug. */
const broken = { now: true }
function Flaky({ name }: { name: string }) {
  if (broken.now) throw new Error(INTERNAL)
  return <p>{name} is fine</p>
}

beforeEach(() => {
  broken.now = true
  localStorage.clear()
  // React and the router log every error they catch; the tests cause them on purpose.
  vi.spyOn(console, 'error').mockImplementation(() => {})
  vi.mocked(reloadPage).mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ErrorBoundary', () => {
  it('shows the fallback instead of an empty page, and tries the children again on request', async () => {
    render(
      <ErrorBoundary
        fallback={(error, reset) => (
          <div>
            <p>fallback for {error.message.slice(0, 6)}</p>
            <button type="button" onClick={reset}>
              retry
            </button>
          </div>
        )}
      >
        <Flaky name="part" />
      </ErrorBoundary>,
    )

    expect(screen.getByText('fallback for secret')).toBeVisible()
    broken.now = false
    await userEvent.click(screen.getByRole('button', { name: 'retry' }))

    expect(screen.getByText('part is fine')).toBeVisible()
    expect(screen.queryByText(/fallback for/)).toBeNull()
  })

  it('stays on the fallback when the retry fails again, and recovers on a later one', async () => {
    render(
      <ErrorBoundary
        fallback={(_error, reset) => (
          <button type="button" onClick={reset}>
            retry
          </button>
        )}
      >
        <Flaky name="part" />
      </ErrorBoundary>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'retry' })) // still broken
    expect(screen.getByRole('button', { name: 'retry' })).toBeVisible()
    broken.now = false
    await userEvent.click(screen.getByRole('button', { name: 'retry' }))

    expect(screen.getByText('part is fine')).toBeVisible()
  })

  it('tries again by itself when its reset key changes (a new address, for instance)', async () => {
    function Host() {
      const [key, setKey] = useState(1)
      return (
        <>
          <button
            type="button"
            onClick={() => {
              broken.now = false
              setKey(2)
            }}
          >
            move on
          </button>
          <ErrorBoundary resetKey={key} fallback={() => <p>broken</p>}>
            <Flaky name="part" />
          </ErrorBoundary>
        </>
      )
    }
    render(<Host />)
    expect(screen.getByText('broken')).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: 'move on' }))

    expect(screen.getByText('part is fine')).toBeVisible()
  })

  it('wraps a thrown value that is not an Error', () => {
    function Throws(): never {
      throw 'just a string'
    }
    render(
      <ErrorBoundary fallback={(error) => <p>{error instanceof Error ? 'wrapped' : 'raw'}</p>}>
        <Throws />
      </ErrorBoundary>,
    )

    expect(screen.getByText('wrapped')).toBeVisible()
  })
})

describe('one part of a page failing', () => {
  it('leaves the sibling parts working, and shows no raw error text', async () => {
    render(
      <LanguageProvider>
        <h1>The page</h1>
        <SectionBoundary>
          <Flaky name="first" />
        </SectionBoundary>
        <SectionBoundary>
          <p>second is fine</p>
        </SectionBoundary>
      </LanguageProvider>,
    )

    expect(screen.getByRole('heading', { level: 1, name: 'The page' })).toBeVisible()
    expect(screen.getByText('second is fine')).toBeVisible()
    const alert = screen.getByRole('alert')
    expect(within(alert).getByRole('heading', { level: 2 })).toHaveTextContent(
      'This part of the page could not be shown',
    )
    expect(document.body).not.toHaveTextContent('secret internal detail')
    expect(within(alert).getByRole('heading', { level: 2 })).toHaveFocus()

    broken.now = false
    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(screen.getByText('first is fine')).toBeVisible()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('says it in Bengali and Hindi too', () => {
    for (const [code, title] of [
      ['bn', 'পৃষ্ঠার এই অংশটি দেখানো যায়নি'],
      ['hi', 'पेज का यह हिस्सा दिखाया नहीं जा सका'],
    ] as const) {
      localStorage.setItem('civicsaathi.ui-language', code)
      const view = render(
        <LanguageProvider>
          <ErrorPanel scope="section" error={new Error(INTERNAL)} onRetry={() => {}} />
        </LanguageProvider>,
      )
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(title)
      view.unmount()
    }
  })

  it('quotes the request id of an API error, and nothing else of it', () => {
    const error = new ApiError(INTERNAL, {
      status: 500,
      code: 'internal_error',
      requestId: 'req-5',
    })
    render(
      <LanguageProvider>
        <ErrorPanel scope="section" error={error} onRetry={() => {}} />
      </LanguageProvider>,
    )

    expect(screen.getByText('Reference: req-5')).toBeVisible()
    expect(document.body).not.toHaveTextContent('secret internal detail')
  })
})

describe('a page failing inside the application frame', () => {
  const Working = () => <p>working page</p>
  const pages = (crashing: Partial<Record<string, () => React.JSX.Element>>) =>
    ((name: string) => ({ Component: crashing[name] ?? Working })) as Parameters<
      typeof renderWithPages
    >[0]

  it('replaces the page with an explanation, keeps the header usable, and recovers on retry', async () => {
    renderWithPages(pages({ SchemesPage: () => <Flaky name="schemes" /> }), '/schemes')

    const alert = await screen.findByRole('alert')
    expect(within(alert).getByRole('heading', { level: 1 })).toHaveTextContent(
      'This page could not be shown',
    )
    expect(alert).not.toHaveTextContent('secret internal detail')
    expect(within(alert).getByRole('link', { name: 'Go to the home page' })).toHaveAttribute(
      'href',
      '/',
    )
    // The frame is still there and still works: the visitor can move on.
    expect(screen.getAllByRole('link', { name: 'Home' }).length).toBeGreaterThan(0)

    broken.now = false
    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('schemes is fine')).toBeVisible()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('lets the visitor leave a failed page by the menu', async () => {
    renderWithPages(pages({ SchemesPage: () => <Flaky name="schemes" /> }), '/schemes')
    await screen.findByRole('alert')

    const nav = screen.getAllByRole('navigation', { name: 'Main' })[0]!
    await userEvent.click(within(nav).getByRole('link', { name: 'Ask AI Saathi' }))

    expect(await screen.findByText('working page')).toBeVisible()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('explains a page whose code could not be fetched, and reloads on retry', async () => {
    const lazyFailure = (name: string) =>
      name === 'SchemesPage'
        ? {
            lazy: async () => {
              throw new TypeError(
                'Failed to fetch dynamically imported module: https://example.org/assets/SchemesPage-abc.js',
              )
            },
          }
        : { Component: Working }
    renderWithPages(lazyFailure as Parameters<typeof renderWithPages>[0], '/schemes')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Check your connection and try again')
    expect(alert).not.toHaveTextContent('example.org')
    expect(vi.mocked(reloadPage)).not.toHaveBeenCalled()

    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(vi.mocked(reloadPage)).toHaveBeenCalledTimes(1)
  })

  it('has no automatically detectable accessibility problems', async () => {
    const { container } = renderWithPages(
      pages({ SchemesPage: () => <Flaky name="schemes" /> }),
      '/schemes',
    )
    await screen.findByRole('alert')

    await expectNoAxeViolations(container)
  })
})

describe('isChunkLoadError', () => {
  it.each([
    'Failed to fetch dynamically imported module: https://x/a.js',
    'Importing a module script failed.',
    'error loading dynamically imported module',
    'Loading chunk 7 failed.',
  ])('recognises the browsers wording: %s', (message) => {
    expect(isChunkLoadError(new TypeError(message))).toBe(true)
  })

  it('does not take an ordinary bug for a failed fetch', () => {
    expect(
      isChunkLoadError(new TypeError("Cannot read properties of undefined (reading 'map')")),
    ).toBe(false)
    expect(isChunkLoadError(undefined)).toBe(false)
  })
})
