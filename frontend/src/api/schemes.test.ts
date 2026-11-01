import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse, stubApi } from '@/test/utils'
import { eligibleBody, schemeDetailsBody, schemesBody } from '@/test/schemeFixtures'
import { ApiError } from './client'
import { checkEligibility, fetchScheme, fetchSchemes } from './schemes'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchSchemes', () => {
  it('returns the list, and asks the server every time whether a kept copy is current', async () => {
    const fetchMock = stubApi({ '/api/v1/schemes': () => jsonResponse(schemesBody) })

    expect(await fetchSchemes()).toEqual(schemesBody.schemes)
    expect(fetchMock.mock.calls[0]?.[1]?.cache).toBe('no-cache')
  })
})

describe('fetchScheme', () => {
  it('returns one scheme, and encodes its id into the address', async () => {
    const fetchMock = stubApi({
      '/api/v1/schemes/svmcm': () => jsonResponse(schemeDetailsBody),
      '/api/v1/schemes/a%20b%2Fc': () => jsonResponse(schemeDetailsBody),
    })

    expect(await fetchScheme('svmcm')).toEqual(schemeDetailsBody)
    await fetchScheme('a b/c')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/schemes/a%20b%2Fc')
  })

  it('fails with the code of the error envelope', async () => {
    stubApi({
      '/api/v1/schemes/ghost': () =>
        jsonResponse(
          { error: { code: 'scheme_not_found', message: 'There is no such scheme.' } },
          { status: 404 },
        ),
    })

    await expect(fetchScheme('ghost')).rejects.toMatchObject({
      status: 404,
      code: 'scheme_not_found',
    })
    await expect(fetchScheme('ghost')).rejects.toBeInstanceOf(ApiError)
  })
})

describe('checkEligibility', () => {
  it('posts the track and answers as JSON, and does not let the browser keep the reply', async () => {
    const fetchMock = stubApi({
      '/api/v1/schemes/svmcm/eligibility': () => jsonResponse(eligibleBody),
    })

    const result = await checkEligibility('svmcm', {
      track: 'ug',
      answers: { family_income: 200000, board_topper: false },
    })

    expect(result).toEqual(eligibleBody)
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    expect(init?.cache).toBe('no-store')
    expect(JSON.parse(String(init?.body))).toEqual({
      track: 'ug',
      answers: { family_income: 200000, board_topper: false },
    })
  })
})
