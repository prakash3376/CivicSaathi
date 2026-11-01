import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderAt } from '@/test/render'
import { schemesBody } from '@/test/schemeFixtures'
import { answerBody, citationBody, jsonResponse, sourcesBody, stubApi } from '@/test/utils'
import type { Answer } from '@/api/types'

const ASK = '/api/v1/assistant/ask'

const fallbackBody: Answer = {
  answerable: false,
  fallback: true,
  language: 'en',
  text: 'The AI service is not answering right now, so no explanation can be written.',
  claims: [],
  citations: [citationBody],
  not_stated: [],
  warnings: [],
  disclaimer: answerBody.disclaimer,
  model: null,
}

function stubChat(replies: Answer[]) {
  const next = [...replies]
  return stubApi({
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    '/api/v1/budget': () => jsonResponse({ records: [] }),
    [ASK]: () => jsonResponse(next.length > 1 ? next.shift()! : next[0]!),
  })
}

const bodies = (mock: ReturnType<typeof stubChat>) =>
  mock.mock.calls
    .filter(([url]) => String(url) === ASK)
    .map(([, init]) => JSON.parse(String(init?.body)) as Record<string, unknown>)

async function ask(question: string) {
  const box = screen.getByRole('textbox', { name: 'Your question' })
  await userEvent.type(box, question)
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.unstubAllGlobals())

describe('follow-up questions', () => {
  it('sends the earlier questions with a later one, so that "it" can be understood', async () => {
    const fetchMock = stubChat([answerBody])
    renderAt('/ask')
    await ask('Tell me about SVMCM')
    await screen.findByRole('heading', { name: 'Answer' })

    await ask('What documents do I need for it?')
    await screen.findAllByRole('heading', { name: 'Answer' })

    const [first, second] = bodies(fetchMock)
    expect(first).not.toHaveProperty('history')
    expect(second?.history).toEqual(['Tell me about SVMCM'])
  })

  it('sends at most the last three, oldest first', async () => {
    const fetchMock = stubChat([answerBody])
    renderAt('/ask')
    for (const question of ['one one', 'two two', 'three three', 'four four', 'five five']) {
      await ask(question)
      await screen.findAllByRole('heading', { name: 'Answer' })
    }

    expect(bodies(fetchMock).at(-1)?.history).toEqual(['two two', 'three three', 'four four'])
  })

  it('forgets them when the conversation is cleared', async () => {
    const fetchMock = stubChat([answerBody])
    renderAt('/ask')
    await ask('Tell me about SVMCM')
    await screen.findByRole('heading', { name: 'Answer' })

    await userEvent.click(screen.getByRole('button', { name: 'Start a new conversation' }))
    await ask('Who can apply?')

    expect(bodies(fetchMock).at(-1)).not.toHaveProperty('history')
  })
})

describe('when the model could not answer', () => {
  it('shows the matching passages, says why, and offers to try again', async () => {
    const fetchMock = stubChat([fallbackBody, answerBody])
    renderAt('/ask')
    await ask('What is the income limit?')

    expect(await screen.findByText(/The AI service is not answering right now/)).toBeVisible()
    expect(screen.getAllByText(citationBody.title).length).toBeGreaterThan(0) // the passage found

    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText(answerBody.claims[0]!.text)).toBeVisible()
    expect(bodies(fetchMock)).toHaveLength(2)
  })

  it('offers no try-again for an ordinary answer', async () => {
    stubChat([answerBody])
    renderAt('/ask')
    await ask('What is the income limit?')
    await screen.findByText(answerBody.claims[0]!.text)

    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
  })
})

describe('the schemes behind an answer', () => {
  it('names the schemes whose documents were cited, with the way on', async () => {
    stubChat([answerBody])
    renderAt('/ask')
    await ask('What is the income limit?')

    const heading = await screen.findByRole('heading', { name: 'The schemes behind this answer' })
    const related = heading.parentElement!

    expect(within(related).getByText('Swami Vivekananda Merit Cum Means Scholarship')).toBeVisible()
    expect(within(related).getByRole('link', { name: /See details/ })).toHaveAttribute(
      'href',
      '/schemes/svmcm',
    )
    expect(within(related).getByRole('link', { name: /Check if I am eligible/ })).toHaveAttribute(
      'href',
      '/schemes/svmcm/check',
    )
  })

  it('names none when the answer cited nothing', async () => {
    stubChat([{ ...answerBody, answerable: false, claims: [], citations: [] }])
    renderAt('/ask')
    await ask('What is the weather?')
    await screen.findByRole('heading', { name: 'Answer' })

    expect(screen.queryByRole('heading', { name: 'The schemes behind this answer' })).toBeNull()
  })
})
