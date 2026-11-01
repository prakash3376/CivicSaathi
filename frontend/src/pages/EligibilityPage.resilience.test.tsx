import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderAt } from '@/test/render'
import { eligibleBody, schemeDetailsBody, schemesBody } from '@/test/schemeFixtures'
import { jsonResponse, sourcesBody, stubApi } from '@/test/utils'

const CHECK = '/api/v1/schemes/svmcm/eligibility'

const unavailable = () =>
  jsonResponse(
    { error: { code: 'schemes_unavailable', message: 'Not available.', request_id: 'req-9' } },
    { status: 503 },
  )

function stubCheck(handler: () => Response | Promise<Response>) {
  return stubApi({
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    '/api/v1/schemes/svmcm': () => jsonResponse(schemeDetailsBody),
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    [CHECK]: handler,
  })
}

const sent = (fetchMock: ReturnType<typeof stubCheck>) =>
  fetchMock.mock.calls
    .filter(([url]) => url === CHECK)
    .map(([, init]) => JSON.parse(String(init?.body)) as unknown)

async function openCheck() {
  renderAt('/schemes/svmcm/check?track=ug')
  await screen.findByRole('heading', { level: 1, name: 'Check your eligibility' })
}

const income = () => screen.getByRole('textbox', { name: 'What is your family income in a year?' })
const marks = () => screen.getByRole('textbox', { name: 'What percentage of marks did you get?' })
const yesNo = (question: string) => screen.getByRole('group', { name: question })

async function fillIn() {
  await userEvent.click(
    within(yesNo('Is your college or university in West Bengal?')).getByRole('radio', {
      name: 'Yes',
    }),
  )
  await userEvent.type(income(), '2,00,000')
  await userEvent.type(marks(), '70')
  await userEvent.click(
    within(yesNo('Did you rank among the toppers of your board?')).getByRole('radio', {
      name: 'No',
    }),
  )
}

beforeEach(() => localStorage.clear())
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('a check that fails', () => {
  it('keeps every answer the person entered, and a retry sends the same answers and succeeds', async () => {
    let calls = 0
    const fetchMock = stubCheck(() => (++calls === 1 ? unavailable() : jsonResponse(eligibleBody)))
    await openCheck()
    await fillIn()

    await userEvent.click(screen.getByRole('button', { name: 'Check' }))
    const alert = await screen.findByRole('alert')

    // Nothing was reset: not the numbers, not the yes/no choices.
    expect(income()).toHaveValue('2,00,000')
    expect(marks()).toHaveValue('70')
    expect(
      within(yesNo('Is your college or university in West Bengal?')).getByRole('radio', {
        name: 'Yes',
      }),
    ).toBeChecked()
    expect(
      within(yesNo('Did you rank among the toppers of your board?')).getByRole('radio', {
        name: 'No',
      }),
    ).toBeChecked()
    expect(screen.queryByRole('heading', { name: 'Your result' })).toBeNull() // no false success
    expect(screen.getByRole('button', { name: 'Check' })).toBeEnabled()

    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))

    await screen.findByRole('heading', { level: 2, name: 'Your result' })
    const bodies = sent(fetchMock)
    expect(bodies).toHaveLength(2)
    expect(bodies[1]).toEqual(bodies[0])
    expect(bodies[0]).toEqual({
      track: 'ug',
      answers: {
        institution_in_west_bengal: true,
        family_income: 200000,
        marks_percent: 70,
        board_topper: false,
      },
    })
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('also keeps the answers when the connection drops, and a result is never invented', async () => {
    const fetchMock = stubCheck(() => jsonResponse(eligibleBody))
    await openCheck()
    await fillIn()
    const online = globalThis.fetch
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
        String(input) === CHECK
          ? Promise.reject(new TypeError('Failed to fetch'))
          : online(input, init),
      ),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Check' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server')
    expect(income()).toHaveValue('2,00,000')
    expect(marks()).toHaveValue('70')
    expect(screen.queryByRole('heading', { name: 'Your result' })).toBeNull()
    expect(sent(fetchMock)).toHaveLength(0) // the stubbed server never saw it
  })

  it('lets an answer be corrected after a failure, and sends the corrected answers', async () => {
    let calls = 0
    const fetchMock = stubCheck(() => (++calls === 1 ? unavailable() : jsonResponse(eligibleBody)))
    await openCheck()
    await fillIn()
    await userEvent.click(screen.getByRole('button', { name: 'Check' }))
    await screen.findByRole('alert')

    await userEvent.clear(marks())
    await userEvent.type(marks(), '85')
    await userEvent.click(screen.getByRole('button', { name: 'Check' }))

    await screen.findByRole('heading', { level: 2, name: 'Your result' })
    expect(
      (sent(fetchMock)[1] as { answers: { marks_percent: number } }).answers.marks_percent,
    ).toBe(85)
    expect(income()).toHaveValue('2,00,000')
  })
})

describe('pressing Check more than once', () => {
  it('sends one request for a double click', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const fetchMock = stubCheck(async () => {
      await held
      return jsonResponse(eligibleBody)
    })
    await openCheck()
    await userEvent.type(marks(), '70')

    await userEvent.dblClick(screen.getByRole('button', { name: 'Check' }))

    expect(sent(fetchMock)).toHaveLength(1)
    release()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })
    expect(sent(fetchMock)).toHaveLength(1)
  })

  it('sends one request when Enter is pressed twice in a field', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const fetchMock = stubCheck(async () => {
      await held
      return jsonResponse(eligibleBody)
    })
    await openCheck()
    await userEvent.type(marks(), '70{Enter}{Enter}')

    expect(sent(fetchMock)).toHaveLength(1)
    release()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })
    expect(sent(fetchMock)).toHaveLength(1)
  })
})
