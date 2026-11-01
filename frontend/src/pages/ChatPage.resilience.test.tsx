import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Answer } from '@/api/types'
import { renderAt } from '@/test/render'
import { schemesBody } from '@/test/schemeFixtures'
import { answerBody, jsonResponse, sourcesBody, stubApi } from '@/test/utils'

const ASK = '/api/v1/assistant/ask'
const QUESTION = 'What is the maximum family income to get the SVMCM scholarship?'

const answerWith = (text: string): Answer => ({
  ...answerBody,
  text,
  claims: [{ text, citations: [1] }],
})

const unavailable = () =>
  jsonResponse(
    { error: { code: 'llm_unavailable', message: 'No answer.', request_id: 'req-3' } },
    { status: 503 },
  )

type Routes = Parameters<typeof stubApi>[0]
function stubChat(routes: Routes) {
  return stubApi({
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    ...routes,
  })
}

const asked = (fetchMock: ReturnType<typeof stubChat>) =>
  fetchMock.mock.calls
    .filter(([url]) => url === ASK)
    .map(([, init]) => JSON.parse(String(init?.body)) as { question: string })

const gate = () => {
  let open!: () => void
  const promise = new Promise<void>((resolve) => {
    open = resolve
  })
  return { promise, open }
}

async function openChat() {
  renderAt('/ask')
  await screen.findByRole('heading', { level: 1, name: /Ask about a scholarship/ })
}

async function ask(question: string) {
  await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), question)
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
}

const turnWith = (question: string) =>
  within(screen.getByRole('region', { name: 'Conversation' }))
    .getByText(question)
    .closest('li') as HTMLElement

beforeEach(() => localStorage.clear())
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('an answer that never comes', () => {
  it('ends in a timeout error that keeps the question and retries into an answer', async () => {
    let calls = 0
    const fetchMock = stubChat({})
    await openChat()
    // The first call to the assistant hangs until it is aborted (as a real request would); the
    // second is answered.
    const original = globalThis.fetch
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) !== ASK) return original(input, init)
        calls += 1
        if (calls > 1) return Promise.resolve(jsonResponse(answerBody))
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          )
        })
      }),
    )
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'], shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })

    await user.type(screen.getByRole('textbox', { name: 'Your question' }), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    expect(screen.getByText('Checking the documents…')).toBeVisible()

    await vi.advanceTimersByTimeAsync(61_000) // past the 60 s the page waits for an answer

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Could not reach the server')
    expect(screen.queryByText('Checking the documents…')).toBeNull() // no spinner left behind
    expect(screen.getByText(QUESTION)).toBeVisible() // the question is still there
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled() // empty box, nothing pending

    await user.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { level: 2, name: 'Answer' })).toBeVisible()
    expect(screen.getAllByText(QUESTION)).toHaveLength(1)
    expect(fetchMock).toBeDefined()
    expect(calls).toBe(2)
  })

  it('lets a new question be typed while a failed one waits for its retry', async () => {
    stubChat({ [ASK]: unavailable })
    await openChat()
    await ask(QUESTION)
    await screen.findByRole('alert')

    const box = screen.getByRole('textbox', { name: 'Your question' })
    await userEvent.type(box, 'Another one')

    expect(box).toHaveValue('Another one')
    expect(screen.getByRole('button', { name: 'Ask' })).toBeEnabled()
    expect(screen.getByText(QUESTION)).toBeVisible()
  })
})

describe('pressing Ask more than once', () => {
  it('sends one request for a double click, and not another while the first is waiting', async () => {
    const held = gate()
    const fetchMock = stubChat({
      [ASK]: async () => {
        await held.promise
        return jsonResponse(answerBody)
      },
    })
    await openChat()
    await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), QUESTION)

    await userEvent.dblClick(screen.getByRole('button', { name: 'Ask' }))
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    expect(asked(fetchMock)).toHaveLength(1)
    held.open()
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    expect(asked(fetchMock)).toHaveLength(1)
    expect(screen.getAllByText(QUESTION)).toHaveLength(1)
  })

  it('does not send the same question twice when Try again is pressed twice quickly', async () => {
    const held = gate()
    let calls = 0
    const fetchMock = stubChat({
      [ASK]: async () => {
        calls += 1
        if (calls === 1) return unavailable()
        await held.promise
        return jsonResponse(answerBody)
      },
    })
    await openChat()
    await ask(QUESTION)
    const alert = await screen.findByRole('alert')

    await userEvent.dblClick(within(alert).getByRole('button', { name: 'Try again' }))

    // The alert is replaced by the wait as soon as the first press is handled: nothing to press again.
    expect(asked(fetchMock)).toHaveLength(2)
    held.open()
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    expect(asked(fetchMock)).toHaveLength(2)
  })
})

describe('answers that arrive out of order', () => {
  it('the retry of an older question does not overwrite the newer one', async () => {
    const retry = gate()
    const calls: Record<string, number> = {}
    stubChat({
      [ASK]: async (call) => {
        const { question } = call.body as { question: string }
        calls[question] = (calls[question] ?? 0) + 1
        if (question === 'First question') {
          if (calls[question] === 1) return unavailable()
          await retry.promise // the retry of the first is slow
          return jsonResponse(answerWith('Answer to the first.'))
        }
        return jsonResponse(answerWith('Answer to the second.'))
      },
    })
    await openChat()
    await ask('First question')
    await screen.findByRole('alert')
    await ask('Second question')
    await screen.findByText('Answer to the second.')

    await userEvent.click(
      within(turnWith('First question')).getByRole('button', { name: 'Try again' }),
    )
    // The older question is waiting again; the newer one has not moved.
    expect(within(turnWith('Second question')).getByText('Answer to the second.')).toBeVisible()
    expect(within(turnWith('First question')).getByText('Checking the documents…')).toBeVisible()
    retry.open()

    expect(await screen.findByText('Answer to the first.')).toBeVisible()
    expect(within(turnWith('First question')).getByText('Answer to the first.')).toBeVisible()
    expect(within(turnWith('Second question')).getByText('Answer to the second.')).toBeVisible()
    expect(within(turnWith('Second question')).queryByText('Answer to the first.')).toBeNull()
    const order = within(screen.getByRole('region', { name: 'Conversation' }))
      .getAllByText(/ question$/)
      .map((node) => node.textContent)
    expect(order).toEqual(['First question', 'Second question'])
  })

  it('an answer that arrives after "new conversation" is ignored', async () => {
    const late = gate()
    stubChat({
      [ASK]: async () => {
        await late.promise
        return jsonResponse(answerWith('A late answer to a forgotten question.'))
      },
    })
    await openChat()
    await ask('A question I will abandon')
    expect(await screen.findByText('Checking the documents…')).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: 'Start a new conversation' }))
    late.open()
    await new Promise((resolve) => setTimeout(resolve, 50)) // let the late reply be handled

    expect(screen.queryByText('A late answer to a forgotten question.')).toBeNull()
    expect(screen.queryByRole('region', { name: 'Conversation' })).toBeNull()
    expect(screen.queryByRole('heading', { level: 2, name: 'Answer' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled() // not stuck on "pending"
  })

  it('a question asked after "new conversation" gets its own answer, not the abandoned one', async () => {
    const late = gate()
    stubChat({
      [ASK]: async (call) => {
        const { question } = call.body as { question: string }
        if (question === 'Abandoned question') {
          await late.promise
          return jsonResponse(answerWith('Answer to the abandoned one.'))
        }
        return jsonResponse(answerWith('Answer to the new one.'))
      },
    })
    await openChat()
    await ask('Abandoned question')
    await userEvent.click(screen.getByRole('button', { name: 'Start a new conversation' }))
    await ask('New question')
    await screen.findByText('Answer to the new one.')

    late.open()
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(screen.queryByText('Answer to the abandoned one.')).toBeNull()
    expect(screen.getByText('Answer to the new one.')).toBeVisible()
    await waitFor(() =>
      expect(screen.getAllByRole('heading', { level: 2, name: 'Answer' })).toHaveLength(1),
    )
  })
})
