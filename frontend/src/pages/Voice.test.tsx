import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { act } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { speaker } from '@/features/voice/speaker'
import { renderAt } from '@/test/render'
import { eligibleBody, schemeDetailsBody, schemesBody } from '@/test/schemeFixtures'
import { installRecognition, installSpeech, resetSpeaker } from '@/test/speech'
import { answerBody, expectNoAxeViolations, jsonResponse, sourcesBody, stubApi } from '@/test/utils'

const ASK = '/api/v1/assistant/ask'
const VOICES = [
  { lang: 'en-IN', name: 'English India' },
  { lang: 'bn-IN', name: 'Bengali India' },
  { lang: 'hi-IN', name: 'Hindi India' },
]

const hindiAnswer = {
  ...answerBody,
  language: 'hi' as const,
  text: 'पारिवारिक आय प्रति वर्ष 2,50,000 रुपये से अधिक नहीं होनी चाहिए।',
  claims: [
    { text: 'पारिवारिक आय प्रति वर्ष 2,50,000 रुपये से अधिक नहीं होनी चाहिए।', citations: [1] },
  ],
  disclaimer: 'यह केवल जानकारी के लिए सारांश है, कानूनी सलाह नहीं।',
}

function stubAll(ask: () => Response = () => jsonResponse(answerBody)) {
  return stubApi({
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    '/api/v1/schemes/svmcm': () => jsonResponse(schemeDetailsBody),
    '/api/v1/schemes/svmcm/eligibility': () => jsonResponse(eligibleBody),
    [ASK]: ask,
  })
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  resetSpeaker()
  speaker.setRate('normal')
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const box = () => screen.getByRole('textbox', { name: /Your question|आपका प्रश्न/ })

describe('speaking a question', () => {
  it('puts the words in the question box after what is there, and sends nothing until Ask', async () => {
    const recognition = installRecognition()
    const fetchMock = stubAll()
    renderAt('/ask')
    await userEvent.type(box(), 'About SVMCM:')

    await userEvent.click(await screen.findByRole('button', { name: 'Speak your question' }))
    act(() => recognition.last()!.hear('what is the income', 'limit'))

    expect(box()).toHaveValue('About SVMCM: what is the income limit')
    await userEvent.click(screen.getByRole('button', { name: 'Stop and use what I said' }))

    expect(box()).toHaveFocus() // so that the words can be checked and edited
    expect(screen.getByText('Please check your question, then press Ask.')).toBeVisible()
    expect(fetchMock.mock.calls.filter(([url]) => url === ASK)).toHaveLength(0)
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    const sent = JSON.parse(String(fetchMock.mock.calls.find(([url]) => url === ASK)?.[1]?.body))
    expect(sent.question).toBe('About SVMCM: what is the income limit')
  })

  it('listens in the language of the answer when one is chosen, else in the language of the page', async () => {
    const recognition = installRecognition()
    stubAll()
    renderAt('/ask')
    const mic = () =>
      screen.getByRole('button', {
        name: /Speak your question|মুখে প্রশ্ন বলুন|बोलकर प्रश्न पूछें/,
      })

    await userEvent.click(await screen.findByRole('button', { name: 'Speak your question' }))
    expect(recognition.last()?.lang).toBe('en-IN') // automatic: the page is in English
    act(() => recognition.last()!.stop())

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Answer language' }),
      'हिन्दी',
    )
    await userEvent.click(mic())
    expect(recognition.last()?.lang).toBe('hi-IN')
    act(() => recognition.last()!.stop())

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Answer language' }),
      'বাংলা',
    )
    await userEvent.click(mic())
    expect(recognition.last()?.lang).toBe('bn-IN')
  })

  it('follows the language of the page when the answer language is automatic', async () => {
    const recognition = installRecognition()
    stubAll()
    renderAt('/ask')
    await userEvent.click(
      within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'हिन्दी' }),
    )

    await userEvent.click(await screen.findByRole('button', { name: 'बोलकर प्रश्न पूछें' }))

    expect(recognition.last()?.lang).toBe('hi-IN')
  })

  it('keeps what was typed within the limit of the question box', async () => {
    const recognition = installRecognition()
    stubAll()
    renderAt('/ask')
    await userEvent.click(await screen.findByRole('button', { name: 'Speak your question' }))

    act(() => recognition.last()!.hear('x'.repeat(700)))

    expect(box()).toHaveValue('x'.repeat(500))
  })

  it('says where the audio goes, next to the microphone', async () => {
    installRecognition()
    stubAll()
    renderAt('/ask')

    expect(
      await screen.findByText(/may send the recording to its own speech service/),
    ).toBeVisible()
  })

  it('leaves typing as it was in a browser that cannot recognise speech', async () => {
    stubAll()
    renderAt('/ask')

    expect(await screen.findByText(/cannot turn speech into text/)).toBeVisible()
    expect(box()).toBeEnabled()
  })
})

describe('talking with the assistant on the page', () => {
  it('asks the spoken question, shows it in the conversation, and reads the answer aloud', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const fetchMock = stubAll()
    renderAt('/ask')
    await userEvent.click(await screen.findByRole('button', { name: 'Start talking' }))
    act(() => speech.finishPiece()) // the prompt
    act(() => recognition.last()!.hear('what is the income limit'))
    await act(async () => recognition.last()!.stop())

    const conversation = await screen.findByRole('region', { name: 'Conversation' })
    expect(within(conversation).getByText('what is the income limit')).toBeVisible()
    expect(
      await within(conversation).findByRole('heading', { level: 2, name: 'Answer' }),
    ).toBeVisible()
    const sent = JSON.parse(String(fetchMock.mock.calls.find(([url]) => url === ASK)?.[1]?.body))
    expect(sent).toEqual({ question: 'what is the income limit', language: 'en' })
    await waitFor(() => expect(speech.spoken()).toHaveLength(2))
    expect(speech.spoken()[1]?.text).toContain('Rs 2,50,000')
  })

  it('answers in Hindi to a question spoken in Hindi, and reads it with the Hindi voice', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    stubAll(() => jsonResponse(hindiAnswer))
    renderAt('/ask')
    await userEvent.click(
      within(screen.getAllByRole('group', { name: 'I will speak in' })[0]!).getByRole('button', {
        name: 'हिन्दी',
      }),
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Start talking' }))
    act(() => speech.finishPiece())
    expect(recognition.last()?.lang).toBe('hi-IN')
    act(() => recognition.last()!.hear('आय की सीमा क्या है'))
    await act(async () => recognition.last()!.stop())

    await waitFor(() => expect(speech.spoken()).toHaveLength(2))
    expect(speech.spoken().at(-1)).toMatchObject({ voice: 'Hindi India', lang: 'hi-IN' })
  })

  it('ends the conversation when the page language is changed', async () => {
    const speech = installSpeech(VOICES)
    installRecognition()
    stubAll()
    renderAt('/ask')
    await userEvent.click(await screen.findByRole('button', { name: 'Start talking' }))
    expect(speech.spoken()).toHaveLength(1)

    await userEvent.click(
      within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'বাংলা' }),
    )

    expect(speaker.getSnapshot().playingId).toBeNull()
    expect(screen.getByRole('button', { name: 'কথা শুরু করুন' })).toBeVisible()
  })
})

describe('listening to an answer', () => {
  it('reads the answer and the disclaimer in the language of the answer', async () => {
    const speech = installSpeech(VOICES)
    stubAll(() => jsonResponse(hindiAnswer))
    renderAt('/ask')
    await userEvent.type(box(), 'आय की सीमा क्या है?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByRole('heading', { level: 2, name: 'Answer' })

    await userEvent.click(screen.getByRole('button', { name: 'Listen to this answer' }))

    const [first] = speech.spoken()
    expect(first).toMatchObject({ voice: 'Hindi India', lang: 'hi-IN' })
    expect(first?.text).toContain('पारिवारिक आय प्रति वर्ष 2,50,000 रुपये')
  })

  it('says so, and leaves the text, when the device has no voice for the answer', async () => {
    installSpeech([{ lang: 'en-IN', name: 'English India' }])
    stubAll(() => jsonResponse(hindiAnswer))
    renderAt('/ask')
    await userEvent.type(box(), 'आय की सीमा क्या है?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByRole('heading', { level: 2, name: 'Answer' })

    expect(screen.getByText(/no Hindi voice/)).toBeVisible()
    expect(screen.getByText(hindiAnswer.claims[0]!.text)).toBeVisible()
  })

  it('stops reading when a new question is asked', async () => {
    installSpeech(VOICES)
    stubAll()
    renderAt('/ask')
    await userEvent.type(box(), 'First question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByRole('heading', { level: 2, name: 'Answer' })
    await userEvent.click(screen.getByRole('button', { name: 'Listen to this answer' }))
    expect(screen.getByRole('button', { name: 'Stop reading' })).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: 'Start a new conversation' }))

    expect(speaker.getSnapshot().playingId).toBeNull()
  })

  it('has no automatically detectable accessibility problems with the voice controls', async () => {
    installSpeech(VOICES)
    installRecognition()
    stubAll()
    const { container } = renderAt('/ask')
    await userEvent.type(box(), 'A question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByRole('heading', { level: 2, name: 'Answer' })

    await expectNoAxeViolations(container)
  })
})

describe('listening to a result and a scheme', () => {
  it('reads an eligibility result aloud', async () => {
    const speech = installSpeech(VOICES)
    stubAll()
    renderAt('/schemes/svmcm/check?track=ug')
    await screen.findByRole('heading', { level: 1, name: 'Check your eligibility' })
    await userEvent.click(screen.getByRole('button', { name: 'Check' }))
    await screen.findByRole('heading', { level: 2, name: 'Your result' })

    await userEvent.click(screen.getByRole('button', { name: 'Listen to this result' }))

    expect(speech.spoken()[0]?.text).toMatch(/^You appear to meet every rule we checked\./)
  })

  it('reads the result in Hindi when the page is in Hindi', async () => {
    const speech = installSpeech(VOICES)
    stubAll()
    renderAt('/schemes/svmcm/check?track=ug')
    await userEvent.click(
      within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'हिन्दी' }),
    )
    await userEvent.click(await screen.findByRole('button', { name: 'जाँचें' }))
    await screen.findByRole('heading', { level: 2, name: 'आपका परिणाम' })

    await userEvent.click(screen.getByRole('button', { name: 'यह परिणाम सुनें' }))

    expect(speech.spoken()[0]).toMatchObject({ voice: 'Hindi India', lang: 'hi-IN' })
    expect(speech.spoken()[0]?.text).toContain('लगता है आप हमारे जाँचे गए सभी नियम पूरे करते हैं')
  })

  it('stops reading the result when the answers are changed and it goes away', async () => {
    installSpeech(VOICES)
    stubAll()
    renderAt('/schemes/svmcm/check?track=ug')
    await screen.findByRole('heading', { level: 1, name: 'Check your eligibility' })
    await userEvent.click(screen.getByRole('button', { name: 'Check' }))
    await screen.findByRole('heading', { level: 2, name: 'Your result' })
    await userEvent.click(screen.getByRole('button', { name: 'Listen to this result' }))

    await userEvent.type(
      screen.getByRole('textbox', { name: 'What percentage of marks did you get?' }),
      '7',
    )

    expect(speaker.getSnapshot().playingId).toBeNull()
  })

  it('reads a scheme aloud, and the other course when another is chosen', async () => {
    const speech = installSpeech(VOICES)
    stubAll()
    renderAt('/schemes/svmcm')
    await screen.findByRole('heading', { level: 1 })

    await userEvent.click(screen.getByRole('button', { name: 'Listen to this scheme' }))
    expect(speech.spoken()[0]?.text).toContain('What you get: Rs 1,000 a month for 10 months.')
    await userEvent.click(screen.getByRole('radio', { name: /Postgraduate/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Listen to this scheme' }))

    const last = speech.spoken().at(-1)
    expect(last?.text).toContain('Rs 2,000 a month for 10 months.')
  })

  it('has no automatically detectable accessibility problems in Hindi', async () => {
    installSpeech(VOICES)
    installRecognition()
    stubAll()
    const { container } = renderAt('/schemes/svmcm')
    await screen.findByRole('heading', { level: 1 })
    await userEvent.click(
      within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'हिन्दी' }),
    )

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'यह योजना सुनें' })).toBeVisible(),
    )
    await expectNoAxeViolations(container)
    expect(within(container).getAllByRole('combobox')[0]).toBeVisible()
  })
})
