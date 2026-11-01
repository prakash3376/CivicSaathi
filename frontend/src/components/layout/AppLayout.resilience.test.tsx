import { act, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithPages } from '@/test/render'
import { expectNoAxeViolations } from '@/test/utils'

const pages = ((_name: string) => ({
  Component: () => <p>a page</p>,
})) as Parameters<typeof renderWithPages>[0]

let online = true
const setOnline = (value: boolean) => {
  online = value
  act(() => {
    window.dispatchEvent(new Event(value ? 'online' : 'offline'))
  })
}

beforeEach(() => {
  online = true
  localStorage.clear()
  vi.spyOn(window.navigator, 'onLine', 'get').mockImplementation(() => online)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the offline notice', () => {
  it('is absent while online', async () => {
    renderWithPages(pages, '/schemes')
    await screen.findByText('a page')

    expect(screen.queryByRole('status')).toBeNull()
  })

  it('appears when the connection goes, says what it means, and goes when it returns', async () => {
    renderWithPages(pages, '/schemes')
    await screen.findByText('a page')

    setOnline(false)

    const notice = screen.getByRole('status')
    expect(notice).toHaveTextContent('You are offline.')
    expect(notice).toHaveTextContent('may be out of date')
    expect(notice).toHaveTextContent('will not work until your connection returns')
    // The page itself is untouched: it is still there to read.
    expect(screen.getByText('a page')).toBeVisible()

    setOnline(true)

    expect(screen.queryByRole('status')).toBeNull()
  })

  it('is shown at once when the page opens while offline', async () => {
    online = false
    renderWithPages(pages, '/schemes')

    expect(await screen.findByRole('status')).toHaveTextContent('You are offline.')
  })

  it('follows each change, not only the first', async () => {
    renderWithPages(pages, '/schemes')
    await screen.findByText('a page')

    setOnline(false)
    setOnline(true)
    setOnline(false)

    expect(screen.getByRole('status')).toBeVisible()
  })

  it('is written in the language of the page', async () => {
    localStorage.setItem('civicsaathi.ui-language', 'bn')
    online = false
    renderWithPages(pages, '/schemes')

    const notice = await screen.findByRole('status')
    expect(notice).toHaveTextContent('আপনি অফলাইনে আছেন।')
    expect(notice).toHaveAttribute('lang', 'bn')
  })

  it('has no automatically detectable accessibility problems', async () => {
    const { container } = renderWithPages(pages, '/schemes')
    await screen.findByText('a page')
    setOnline(false)

    await expectNoAxeViolations(container)
  })
})
