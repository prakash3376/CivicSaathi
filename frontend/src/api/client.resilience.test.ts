import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse } from '@/test/utils'
import { ApiError, apiFetch } from './client'

const RAW_HTML =
  '<html><body><h1>502 Bad Gateway</h1><pre>nginx/1.25 at /var/www/x</pre></body></html>'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const reply = (response: () => Response) =>
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => response()),
  )

async function failure(): Promise<ApiError> {
  try {
    await apiFetch('/x')
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError)
    return error as ApiError
  }
  throw new Error('the call did not fail')
}

const STATUSES = [400, 401, 403, 404, 408, 409, 429, 500, 502, 503] as const

describe('every failure status becomes an ApiError', () => {
  it.each(STATUSES)(
    '%i with the API error envelope keeps its status, code, words and id',
    async (status) => {
      reply(() =>
        jsonResponse(
          {
            error: { code: `code_${status}`, message: `Words for ${status}.`, request_id: 'req-1' },
          },
          { status },
        ),
      )

      const error = await failure()

      expect(error).toMatchObject({
        status,
        code: `code_${status}`,
        message: `Words for ${status}.`,
        requestId: 'req-1',
      })
    },
  )

  it.each(STATUSES)('%i with an HTML page from a proxy never shows the page', async (status) => {
    reply(() => new Response(RAW_HTML, { status, headers: { 'X-Request-ID': 'req-2' } }))

    const error = await failure()

    expect(error.status).toBe(status)
    expect(error.code).toBe('http_error')
    expect(error.requestId).toBe('req-2')
    expect(error.message).not.toMatch(/nginx|<html|Bad Gateway|\/var\/www/)
    expect(error.message.length).toBeGreaterThan(10)
  })

  it.each(STATUSES)('%i with an empty body is still a readable ApiError', async (status) => {
    reply(() => new Response(null, { status }))

    const error = await failure()

    expect(error).toMatchObject({ status, code: 'http_error' })
    expect(error.message).not.toBe('')
  })

  it('says "try again in a moment" for a server fault and gives the status for a client one', async () => {
    reply(() => new Response(RAW_HTML, { status: 503 }))
    expect((await failure()).message).toMatch(/try again in a moment/i)

    reply(() => new Response(RAW_HTML, { status: 409 }))
    expect((await failure()).message).toContain('409')
  })

  it('does not take a JSON body without an error envelope for one', async () => {
    reply(() =>
      jsonResponse({ detail: 'Traceback (most recent call last): secret' }, { status: 500 }),
    )

    const error = await failure()

    expect(error.code).toBe('http_error')
    expect(error.message).not.toMatch(/Traceback|secret/)
  })
})

describe('no answer, or an answer that cannot be read', () => {
  it('a timeout is code "timeout" with no status, and the request is aborted', async () => {
    vi.useFakeTimers()
    let aborted = false
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => {
              aborted = true
              reject(new DOMException('Aborted', 'AbortError'))
            })
          }),
      ),
    )

    const result = apiFetch('/slow', { timeoutMs: 50 }).catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(50)

    expect(await result).toMatchObject({ code: 'timeout', status: 0 })
    expect(aborted).toBe(true)
  })

  it('a network failure is code "network_error" with no status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    expect(await failure()).toMatchObject({ code: 'network_error', status: 0 })
  })

  it.each([
    ['an empty body', () => new Response('', { status: 200 })],
    ['plain text', () => new Response('OK', { status: 200 })],
    [
      'the single-page app shell served in place of the API',
      () => new Response(RAW_HTML, { status: 200 }),
    ],
    ['a 204 with no content', () => new Response(null, { status: 204 })],
  ])('a successful status with %s is code "invalid_response"', async (_name, make) => {
    reply(make)

    expect(await failure()).toMatchObject({ code: 'invalid_response' })
  })

  it('a timeout while the body is being read is still a timeout, not a crash', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        const body = new ReadableStream({
          start(controller) {
            init?.signal?.addEventListener('abort', () =>
              controller.error(new DOMException('Aborted', 'AbortError')),
            )
          },
        })
        return new Response(body, { status: 200 })
      }),
    )

    const result = apiFetch('/slow-body', { timeoutMs: 50 }).catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(50)

    expect(await result).toMatchObject({ code: 'timeout' })
  })
})

describe('what a failure never contains', () => {
  it('is never thrown as anything but an ApiError, unless the caller cancelled', async () => {
    const cases: (() => Response | Promise<Response>)[] = [
      () => new Response(RAW_HTML, { status: 500 }),
      () => new Response('not json', { status: 200 }),
      () => {
        throw new TypeError('Failed to fetch')
      },
    ]
    for (const make of cases) {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => make()),
      )
      await expect(apiFetch('/x')).rejects.toBeInstanceOf(ApiError)
    }
  })
})
