import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createTestQueryClient, healthBody, jsonResponse } from '@/test/utils'
import { HealthStatus } from './HealthStatus'

function renderStatus() {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <HealthStatus />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('HealthStatus', () => {
  it('shows what the server reports once connected', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async () => jsonResponse(healthBody)),
    )

    renderStatus()

    expect(screen.getByRole('status')).toHaveTextContent('Checking the server')
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('0.1.0')).toBeInTheDocument()
    expect(screen.getByText('development')).toBeInTheDocument()
    expect(screen.getByText('2 min')).toBeInTheDocument()
  })

  it('explains a failure, shows the reference, and lets the user try again', async () => {
    const failure = {
      error: {
        code: 'internal_error',
        message: 'Something went wrong on our side. Please try again.',
        request_id: 'req-42',
      },
    }
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(async () => jsonResponse(failure, { status: 500 }))
      .mockImplementationOnce(async () => jsonResponse(healthBody))
    vi.stubGlobal('fetch', fetchMock)

    renderStatus()

    expect(await screen.findByText('Server unavailable')).toBeInTheDocument()
    expect(screen.getByText(failure.error.message)).toBeInTheDocument()
    expect(screen.getByText('req-42')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
