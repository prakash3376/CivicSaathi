import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse } from '@/test/utils'
import { apiFetch } from './client'

type FetchImpl = (input: string, init?: RequestInit) => Promise<Response>

function stubFetch(impl: FetchImpl) {
  const fetchMock = vi.fn(impl)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** A request that never completes on its own; it only ends when its signal is aborted. */
const hangUntilAborted: FetchImpl = (_input, init) =>
  new Promise((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  })

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('apiFetch', () => {
  it('returns the parsed JSON body and asks for JSON', async () => {
    const fetchMock = stubFetch(async () => jsonResponse({ hello: 'world' }))

    await expect(apiFetch('/api/v1/thing')).resolves.toEqual({ hello: 'world' })

    const [url, init] = fetchMock.mock.lastCall ?? []
    expect(url).toBe('/api/v1/thing')
    expect(new Headers(init?.headers).get('Accept')).toBe('application/json')
  })

  it('turns an API error reply into an ApiError', async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: 'unreadable_scan',
            message: 'Please upload a clearer photo.',
            request_id: 'abc123',
          },
        },
        { status: 422 },
      ),
    )

    await expect(apiFetch('/x')).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      code: 'unreadable_scan',
      message: 'Please upload a clearer photo.',
      requestId: 'abc123',
    })
  })

  it('falls back to a generic error when the failure reply is not JSON', async () => {
    stubFetch(
      async () =>
        new Response('<html>Bad gateway</html>', {
          status: 502,
          headers: { 'X-Request-ID': 'req-9' },
        }),
    )

    await expect(apiFetch('/x')).rejects.toMatchObject({
      status: 502,
      code: 'http_error',
      message: expect.stringMatching(/try again/i),
      requestId: 'req-9',
    })
  })

  it('reports an unreadable success reply', async () => {
    stubFetch(async () => new Response('not json', { status: 200 }))

    await expect(apiFetch('/x')).rejects.toMatchObject({ code: 'invalid_response' })
  })

  it('reports a network failure', async () => {
    stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })

    await expect(apiFetch('/x')).rejects.toMatchObject({ status: 0, code: 'network_error' })
  })

  it('gives up after the timeout', async () => {
    vi.useFakeTimers()
    stubFetch(hangUntilAborted)

    const result = expect(apiFetch('/slow', { timeoutMs: 100 })).rejects.toMatchObject({
      status: 0,
      code: 'timeout',
    })
    await vi.advanceTimersByTimeAsync(100)

    await result
  })

  it('rethrows the abort, not an ApiError, when the caller cancels', async () => {
    stubFetch(hangUntilAborted)
    const controller = new AbortController()

    const result = expect(apiFetch('/x', { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    })
    controller.abort()

    await result
  })
})
