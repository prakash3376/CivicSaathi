import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderAt } from '@/test/render'
import { schemesBody } from '@/test/schemeFixtures'
import {
  answerBody,
  expectNoAxeViolations,
  jsonResponse,
  notCoveredBody,
  sourcesBody,
  stubApi,
} from '@/test/utils'

const ASK = '/api/v1/assistant/ask'
const SOURCES = '/api/v1/sources'
const SCHEMES = '/api/v1/schemes'
const QUESTION = 'What is the maximum family income to get the SVMCM scholarship?'

type Routes = Parameters<typeof stubApi>[0]

function stubChat(routes: Routes = {}) {
  return stubApi({
    [SOURCES]: () => jsonResponse(sourcesBody),
    [SCHEMES]: () => jsonResponse(schemesBody),
    ...routes,
  })
}

async function openChat(path = '/ask') {
  const view = renderAt(path)
  await screen.findByRole('heading', { level: 1, name: /Ask about a scholarship|বৃত্তি সম্পর্কে/ })
  return view
}

async function ask(question = QUESTION) {
  await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), question)
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
}

const asked = (fetchMock: ReturnType<typeof stubChat>) =>
  fetchMock.mock.calls
    .filter(([url]) => url === ASK)
    .map(([, init]) => JSON.parse(String(init?.body)) as Record<string, unknown>)

const failure = (code: string, message: string, status: number, requestId = 'req-7') =>
  jsonResponse({ error: { code, message, request_id: requestId } }, { status })

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('the documents it answers from', () => {
  it('lists each source with its date, when it was verified, and what to be careful about', async () => {
    stubChat()
    await openChat()

    const library = await screen.findByRole('region', {
      name: 'Documents the assistant answers from',
    })
    const titles = await within(library).findAllByRole('heading', { level: 3 })
    expect(titles.map((title) => title.textContent)).toEqual([
      'SVMCM Scholarship: Guidelines (opens the official document in a new tab)',
      'AICTE Pragati: Notification 2026-27 (opens the official document in a new tab)',
    ])
    expect(within(library).getByText('More than 12 months old')).toBeInTheDocument()
    expect(within(library).getByText('Read from a scan: check the figures')).toBeInTheDocument()
    expect(within(library).getByText('Due for a new check')).toBeInTheDocument()
  })

  it('says so when the list cannot be loaded, and can try again', async () => {
    const sources = vi
      .fn()
      .mockImplementationOnce(() => failure('index_unavailable', 'Not ready.', 503))
      .mockImplementation(() => jsonResponse(sourcesBody))
    stubChat({ [SOURCES]: sources })
    await openChat()

    expect(
      await screen.findByText('The list of documents could not be loaded.'),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('SVMCM Scholarship: Guidelines')).toBeInTheDocument()
  })

  it('says so when there are none', async () => {
    stubChat({ [SOURCES]: () => jsonResponse({ sources: [] }) })
    await openChat()

    expect(await screen.findByText('No documents have been added yet.')).toBeInTheDocument()
  })
})

describe('a conversation', () => {
  it('sends the trimmed question and the language, then shows the question and its answer', async () => {
    const fetchMock = stubChat({ [ASK]: () => jsonResponse(answerBody) })
    await openChat()

    await ask(`  ${QUESTION}  `)

    const conversation = await screen.findByRole('region', { name: 'Conversation' })
    expect(within(conversation).getByText(QUESTION)).toBeVisible()
    expect(within(conversation).getByRole('heading', { level: 2, name: 'Answer' })).toBeVisible()
    expect(within(conversation).getByText(answerBody.claims[0]!.text)).toBeVisible()
    expect(within(conversation).getByRole('button', { name: 'Source 1' })).toBeVisible()
    expect(asked(fetchMock)).toEqual([{ question: QUESTION, language: 'auto' }])
  })

  it('keeps every exchange, in order, and empties the box for the next question', async () => {
    stubChat({
      [ASK]: () => jsonResponse(answerBody),
    })
    await openChat()

    await ask('First question')
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue('')
    await ask('Second question')

    await waitFor(() =>
      expect(screen.getAllByRole('heading', { level: 2, name: 'Answer' })).toHaveLength(2),
    )
    const transcript = screen
      .getByRole('region', { name: 'Conversation' })
      .querySelector(':scope > ol')
    const turns = Array.from(transcript?.children ?? [])
    expect(turns).toHaveLength(2)
    expect(turns[0]).toHaveTextContent('First question')
    expect(turns[0]).not.toHaveTextContent('Second question')
    expect(turns[1]).toHaveTextContent('Second question')
  })

  it('cancels a question still waiting for its answer when the page is left', async () => {
    const fetchMock = stubChat({ [ASK]: () => new Promise<Response>(() => {}) })
    const { unmount } = await openChat()
    await ask()
    expect(await screen.findByText('Checking the documents…')).toBeVisible()
    const signal = fetchMock.mock.calls.find(([url]) => url === ASK)?.[1]?.signal

    expect(signal?.aborted).toBe(false)
    unmount()

    expect(signal?.aborted).toBe(true)
  })

  it('cannot be submitted while the question is empty', async () => {
    stubChat()
    await openChat()
    const button = screen.getByRole('button', { name: 'Ask' })

    expect(button).toBeDisabled()
    await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), '   ')
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), 'income')
    expect(button).toBeEnabled()
  })

  it('announces the wait, keeps the button off, and moves to the answer when it arrives', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    stubChat({
      [ASK]: async () => {
        await gate
        return jsonResponse(answerBody)
      },
    })
    await openChat()
    await screen.findByText('SVMCM Scholarship: Guidelines')

    await ask()

    expect(screen.getByText('Checking the documents…')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
    release()
    const heading = await screen.findByRole('heading', { level: 2, name: 'Answer' })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(screen.queryByText('Checking the documents…')).not.toBeInTheDocument()
  })

  it('shows a clear message, and no sources, when the documents do not say', async () => {
    stubChat({ [ASK]: () => jsonResponse(notCoveredBody) })
    await openChat()

    await ask('What is the capital of France?')

    expect(await screen.findByText(/do not say this/)).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Sources for this answer' }),
    ).not.toBeInTheDocument()
  })

  it('starts a new conversation on request, forgetting the old one', async () => {
    stubChat({ [ASK]: () => jsonResponse(answerBody) })
    await openChat()
    await ask('A question of my own')
    await screen.findByRole('heading', { level: 2, name: 'Answer' })

    await userEvent.click(screen.getByRole('button', { name: 'Start a new conversation' }))

    expect(screen.queryByRole('region', { name: 'Conversation' })).not.toBeInTheDocument()
    expect(screen.queryByText('A question of my own')).not.toBeInTheDocument()
  })

  it('offers example questions only before the first one, and they fill in the box', async () => {
    stubChat({ [ASK]: () => jsonResponse(answerBody) })
    await openChat()
    const example = 'Who can apply for the AICTE Pragati scholarship?'

    await userEvent.click(screen.getByRole('button', { name: example }))

    const box = screen.getByRole('textbox', { name: 'Your question' })
    expect(box).toHaveValue(example)
    expect(box).toHaveFocus()
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    expect(screen.queryByRole('button', { name: example })).not.toBeInTheDocument()
  })

  it('counts the characters, and asks people not to type ID numbers', async () => {
    stubChat()
    await openChat()
    const box = screen.getByRole('textbox', { name: 'Your question' })

    await userEvent.type(box, 'income')

    expect(screen.getByText('6 of 500 characters')).toBeInTheDocument()
    expect(box).toHaveAccessibleDescription(/do not type ID, bank or phone numbers/)
    expect(box).toHaveAttribute('maxlength', '500')
  })
})

describe('asking about one scheme', () => {
  it('limits the answer to the documents of the scheme in the address', async () => {
    const fetchMock = stubChat({ [ASK]: () => jsonResponse(answerBody) })
    await openChat('/ask?scheme=svmcm')

    expect(await screen.findByRole('combobox', { name: 'Ask about' })).toHaveValue('svmcm')
    expect(
      screen.getByText(
        'Answers will come only from the documents of Swami Vivekananda Merit Cum Means Scholarship.',
      ),
    ).toBeVisible()
    await ask()
    await screen.findByRole('heading', { level: 2, name: 'Answer' })

    expect(asked(fetchMock)).toEqual([
      {
        question: QUESTION,
        language: 'auto',
        source_ids: ['wb-svmcm-guidelines', 'wb-svmcm-scheme-page'],
      },
    ])
  })

  it('can be changed to a scheme, and back to all documents', async () => {
    const fetchMock = stubChat({ [ASK]: () => jsonResponse(answerBody) })
    const { router } = await openChat()
    const scope = await screen.findByRole('combobox', { name: 'Ask about' })
    expect(scope).toHaveValue('')

    await userEvent.selectOptions(scope, 'AICTE Pragati Scholarship for Girls')
    expect(router.state.location.search).toBe('?scheme=aicte-pragati')
    await ask('One')
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    await userEvent.selectOptions(scope, 'All documents')
    expect(router.state.location.search).toBe('')
    await ask('Two')
    await waitFor(() => expect(asked(fetchMock)).toHaveLength(2))

    expect(asked(fetchMock)[0]).toMatchObject({ source_ids: ['aicte-pragati-faq'] })
    expect(asked(fetchMock)[1]).not.toHaveProperty('source_ids')
  })

  it('ignores a scheme in the address that does not exist', async () => {
    const fetchMock = stubChat({ [ASK]: () => jsonResponse(answerBody) })
    await openChat('/ask?scheme=ghost')

    expect(await screen.findByRole('combobox', { name: 'Ask about' })).toHaveValue('')
    await ask()
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    expect(asked(fetchMock)[0]).not.toHaveProperty('source_ids')
  })

  it('does not offer a choice of scheme if the list of schemes is not available', async () => {
    stubChat({ [SCHEMES]: () => failure('schemes_unavailable', 'x', 503) })
    await openChat()

    await screen.findByRole('textbox', { name: 'Your question' })
    expect(screen.queryByRole('combobox', { name: 'Ask about' })).not.toBeInTheDocument()
  })
})

describe('when something goes wrong', () => {
  it('explains, quotes the reference, and lets the user try the same question again', async () => {
    const answer = vi
      .fn()
      .mockImplementationOnce(() =>
        failure('llm_unavailable', 'The assistant did not respond.', 503),
      )
      .mockImplementation(() => jsonResponse(answerBody))
    const fetchMock = stubChat({ [ASK]: answer })
    await openChat()

    await ask()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('We could not get an answer')
    expect(alert).toHaveTextContent(
      'The assistant is not available right now. Please try again later.',
    )
    expect(alert).toHaveTextContent('Reference: req-7')
    await waitFor(() => expect(alert).toHaveFocus())

    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { level: 2, name: 'Answer' })).toBeInTheDocument()
    const sent = asked(fetchMock)
    expect(sent).toHaveLength(2)
    expect(sent[1]).toEqual(sent[0])
    expect(screen.getAllByText(QUESTION)).toHaveLength(1) // the same turn, not a new one
  })

  it('tells someone who asks too fast to wait', async () => {
    stubChat({ [ASK]: () => failure('rate_limited', 'You are asking too quickly.', 429) })
    await openChat()

    await ask()

    expect(await screen.findByRole('alert')).toHaveTextContent('Please wait a minute and try again')
  })

  it('tells someone who is offline to check their connection', async () => {
    stubChat()
    const online = globalThis.fetch
    await openChat()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === ASK) return Promise.reject(new TypeError('Failed to fetch'))
        return online(input, init)
      }),
    )

    await ask()

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server')
  })

  it("shows the server's own words for a problem it has no special wording for", async () => {
    stubChat({
      [ASK]: () =>
        failure('question_too_long', 'Please keep the question under 400 characters.', 422),
    })
    await openChat()

    await ask()

    expect(await screen.findByRole('alert')).toHaveTextContent('under 400 characters')
  })
})

describe('Bengali', () => {
  it('switches the whole page to Bengali with the switch in the header, and remembers the choice', async () => {
    stubChat({ [ASK]: () => jsonResponse(answerBody) })
    const { unmount } = await openChat()

    await userEvent.click(
      within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'বাংলা' }),
    )

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'বৃত্তি সম্পর্কে প্রশ্ন করুন',
    )
    expect(screen.getByRole('textbox', { name: 'আপনার প্রশ্ন' })).toBeInTheDocument()
    expect(document.title).toContain('বৃত্তি সম্পর্কে প্রশ্ন করুন')
    expect(document.documentElement.lang).toBe('bn')
    expect(screen.getByRole('combobox', { name: 'কোন বিষয়ে প্রশ্ন' })).toBeInTheDocument()

    unmount()
    renderAt('/ask') // a later visit
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'বৃত্তি সম্পর্কে প্রশ্ন করুন',
    )
  })

  it('keeps the language of the answer apart from the language of the page', async () => {
    const fetchMock = stubChat({ [ASK]: () => jsonResponse(answerBody) })
    await openChat()

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Answer language' }),
      'বাংলা',
    )
    await ask('আয়ের সীমা কত?')
    await screen.findByRole('heading', { level: 2, name: 'Answer' })

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ask about a scholarship')
    expect(asked(fetchMock)).toEqual([{ question: 'আয়ের সীমা কত?', language: 'bn' }])
  })

  it('offers example questions in Bengali', async () => {
    stubChat()
    await openChat()

    await userEvent.click(
      within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'বাংলা' }),
    )

    expect(
      screen.getByRole('button', { name: /SVMCM বৃত্তি পেতে পরিবারের সর্বোচ্চ আয়/ }),
    ).toBeInTheDocument()
  })

  it('stays in English when the answer language is automatic, and sends "auto"', async () => {
    const fetchMock = stubChat({ [ASK]: () => jsonResponse(answerBody) })
    await openChat()

    await ask('আয়ের সীমা কত?')
    await screen.findByRole('heading', { level: 2, name: 'Answer' })

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ask about a scholarship')
    expect(asked(fetchMock)[0]).toMatchObject({ language: 'auto' })
  })

  it('ignores corrupt remembered choices', async () => {
    localStorage.setItem('civicsaathi.language', 'klingon')
    localStorage.setItem('civicsaathi.ui-language', 'klingon')
    stubChat()

    await openChat()

    expect(screen.getByRole('combobox', { name: 'Answer language' })).toHaveValue('auto')
    expect(document.documentElement.lang).toBe('en')
  })

  it('still works when the browser will not store anything', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    stubChat()
    await openChat()

    await userEvent.click(
      within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'বাংলা' }),
    )

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'বৃত্তি সম্পর্কে প্রশ্ন করুন',
    )
  })
})

describe('privacy', () => {
  it('stores only the two language choices, never a question or an answer', async () => {
    stubChat({ [ASK]: () => jsonResponse(answerBody) })
    await openChat()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Answer language' }), 'en')
    await userEvent.click(
      within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'English' }),
    )
    await ask('my private question')
    await screen.findByRole('heading', { level: 2, name: 'Answer' })

    expect(Object.keys(localStorage).sort()).toEqual([
      'civicsaathi.language',
      'civicsaathi.ui-language',
    ])
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain('private')
    expect(screen.getByText('The conversation stays on this page and is not saved.')).toBeVisible()
  })
})

describe('accessibility', () => {
  it('has no automatically detectable problems, before and after an answer', async () => {
    stubChat({
      [ASK]: () =>
        jsonResponse({
          ...answerBody,
          warnings: [{ code: 'stale', message: 'Old.', source_ids: [] }],
        }),
    })
    const { container } = await openChat('/ask?scheme=svmcm')
    await screen.findByText('SVMCM Scholarship: Guidelines')
    await expectNoAxeViolations(container)

    await ask()
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    await expectNoAxeViolations(container)
  })

  it('has no automatically detectable problems with several answers, and gives them no landmarks of their own', async () => {
    stubChat({ [ASK]: () => jsonResponse(answerBody) })
    const { container } = await openChat()
    await ask('First question')
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    await ask('Second question')
    await waitFor(() =>
      expect(
        screen.getAllByRole('heading', { level: 3, name: 'Sources for this answer' }),
      ).toHaveLength(2),
    )

    // Two answers with the same parts must not make two regions of the same name.
    const transcript = within(screen.getByRole('region', { name: 'Conversation' }))
    expect(transcript.queryByRole('region', { name: 'Sources for this answer' })).toBeNull()
    await expectNoAxeViolations(container)
  })

  it('has no automatically detectable problems in Bengali, or after an error', async () => {
    stubChat({ [ASK]: () => failure('llm_busy', 'Busy.', 429) })
    const { container } = await openChat()
    await userEvent.click(
      within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'বাংলা' }),
    )
    await screen.findByText('SVMCM Scholarship: Guidelines')
    await userEvent.type(screen.getByRole('textbox', { name: 'আপনার প্রশ্ন' }), 'আয়ের সীমা কত?')
    await userEvent.click(screen.getByRole('button', { name: 'জিজ্ঞাসা করুন' }))
    await screen.findByRole('alert')

    await expectNoAxeViolations(container)
  })

  it('gives every control a touch target of at least 48 pixels', async () => {
    stubChat()
    await openChat()
    await screen.findByText('SVMCM Scholarship: Guidelines')

    const controls = [
      ...screen.getAllByRole('button'),
      ...screen.getAllByRole('combobox'),
      screen.getByRole('textbox'),
    ]

    for (const control of controls) expect(control.className, control.outerHTML).toMatch(/min-h-12/)
  })
})
