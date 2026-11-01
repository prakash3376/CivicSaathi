import { env } from '@/config/env'
import type { ApiErrorBody } from './types'

const DEFAULT_TIMEOUT_MS = 15_000

/** A failed API call, whether the server answered with an error or never answered at all. */
export class ApiError extends Error {
  /** HTTP status, or 0 when no response was received. */
  readonly status: number
  /** Stable identifier: from the API (`not_found`) or the client (`network_error`, `timeout`). */
  readonly code: string
  /** Quote this when reporting a problem; it matches the id in the server logs. */
  readonly requestId: string | undefined

  constructor(message: string, details: { status: number; code: string; requestId?: string }) {
    super(message)
    this.name = 'ApiError'
    this.status = details.status
    this.code = details.code
    this.requestId = details.requestId
  }
}

export interface RequestOptions extends Omit<RequestInit, 'signal'> {
  /** Cancels the request, for example when the component that asked for it unmounts. */
  signal?: AbortSignal
  /** Give up after this long. Raise it for slow operations such as document processing. */
  timeoutMs?: number
}

const timeoutError = () =>
  new ApiError('The server took too long to respond.', { status: 0, code: 'timeout' })

/** Call a JSON endpoint of the CivicSaathi API. Every failure is thrown as an {@link ApiError}. */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { signal, timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = options

  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const abortWithCaller = () => controller.abort(signal?.reason)
  if (signal?.aborted) abortWithCaller()
  else signal?.addEventListener('abort', abortWithCaller, { once: true })

  try {
    const headers = new Headers(init.headers)
    if (!headers.has('Accept')) headers.set('Accept', 'application/json')

    let response: Response
    try {
      response = await fetch(`${env.apiBaseUrl}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
      })
    } catch (error) {
      if (signal?.aborted) throw error // the caller gave up; that is not a failure to report
      if (timedOut) throw timeoutError()
      throw new ApiError('Could not reach the server. Check your connection and try again.', {
        status: 0,
        code: 'network_error',
      })
    }

    if (!response.ok) throw await errorFromResponse(response)

    try {
      return (await response.json()) as T
    } catch {
      throw timedOut
        ? timeoutError()
        : new ApiError('The server sent a reply we could not read.', {
            status: response.status,
            code: 'invalid_response',
          })
    }
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', abortWithCaller)
  }
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  const headerRequestId = response.headers.get('X-Request-ID') ?? undefined
  try {
    const body = (await response.json()) as Partial<ApiErrorBody>
    if (body.error) {
      const { code, message, request_id } = body.error
      return new ApiError(message, {
        status: response.status,
        code,
        requestId: request_id ?? headerRequestId,
      })
    }
  } catch {
    // The body was not JSON (for example an HTML error page from a proxy): use the generic error.
  }
  const message =
    response.status >= 500
      ? 'The service is having trouble right now. Please try again in a moment.'
      : `The request could not be completed (HTTP ${response.status}).`
  return new ApiError(message, {
    status: response.status,
    code: 'http_error',
    requestId: headerRequestId,
  })
}
