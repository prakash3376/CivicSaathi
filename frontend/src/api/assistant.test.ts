import { afterEach, describe, expect, it, vi } from 'vitest'
import { answerBody, jsonResponse, sourcesBody, stubApi } from '@/test/utils'
import { askQuestion, fetchSources } from './assistant'
import { ApiError } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('askQuestion', () => {
  it('posts the question and language as JSON and returns the answer', async () => {
    const fetchMock = stubApi({ '/api/v1/assistant/ask': () => jsonResponse(answerBody) })

    const answer = await askQuestion({ question: 'What is the income limit?', language: 'bn' })

    expect(answer).toEqual(answerBody)
    const [url, init] = fetchMock.mock.calls[0] ?? []
    expect(url).toBe('/api/v1/assistant/ask')
    expect(init?.method).toBe('POST')
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json')
    expect(JSON.parse(String(init?.body))).toEqual({
      question: 'What is the income limit?',
      language: 'bn',
    })
  })

  it('is never cached, because an answer belongs to one question', async () => {
    const fetchMock = stubApi({ '/api/v1/assistant/ask': () => jsonResponse(answerBody) })

    await askQuestion({ question: 'q', language: 'auto' })

    expect(fetchMock.mock.calls[0]?.[1]?.cache).toBe('no-store')
  })

  it('turns an error reply into an ApiError with its code and request id', async () => {
    stubApi({
      '/api/v1/assistant/ask': () =>
        jsonResponse(
          { error: { code: 'rate_limited', message: 'Too fast.', request_id: 'req-9' } },
          { status: 429 },
        ),
    })

    const failure = await askQuestion({ question: 'q', language: 'en' }).catch(
      (error: unknown) => error,
    )

    expect(failure).toBeInstanceOf(ApiError)
    expect(failure).toMatchObject({ status: 429, code: 'rate_limited', requestId: 'req-9' })
  })
})

describe('fetchSources', () => {
  it('returns the list of sources', async () => {
    stubApi({ '/api/v1/sources': () => jsonResponse(sourcesBody) })

    await expect(fetchSources()).resolves.toEqual(sourcesBody.sources)
  })
})
