import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderAt } from '@/test/render'
import { schemesBody } from '@/test/schemeFixtures'
import { jsonResponse, sourcesBody, stubApi } from '@/test/utils'

// The conversation area is made to fail while rendering; the rest of the page is the real one.
const crash = { now: true }
vi.mock('@/features/assistant/ChatSection', () => ({
  ChatSection: () => {
    if (crash.now) throw new Error('secret internal detail in the conversation')
    return <p>the conversation is back</p>
  },
}))

beforeEach(() => {
  crash.now = true
  localStorage.clear()
  vi.spyOn(console, 'error').mockImplementation(() => {})
  stubApi({
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    '/api/v1/schemes': () => jsonResponse(schemesBody),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('a crash in the assistant conversation', () => {
  it('leaves the heading, the documents list and the menu, and says what failed', async () => {
    renderAt('/ask')

    expect(
      await screen.findByRole('heading', { level: 1, name: /Ask about a scholarship/ }),
    ).toBeVisible()
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('This part of the page could not be shown')
    expect(alert).toHaveTextContent('The rest of the page still works')
    expect(document.body).not.toHaveTextContent('secret internal detail')
    // The documents the assistant answers from are not part of the failure.
    expect(
      await screen.findByRole('region', { name: 'Documents the assistant answers from' }),
    ).toBeVisible()
    // Nor is the page frame.
    expect(screen.getAllByRole('link', { name: 'Explore Schemes' }).length).toBeGreaterThan(0)
  })

  it('starts the conversation again when asked to try again', async () => {
    renderAt('/ask')
    const alert = await screen.findByRole('alert')

    crash.now = false
    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('the conversation is back')).toBeVisible()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
