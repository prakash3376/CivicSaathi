import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Answer, AskRequest } from '@/api/types'
import type { TurnState } from '@/features/assistant/useChat'
import { installRecognition, installSpeech, resetSpeaker } from '@/test/speech'
import { answerBody, expectNoAxeViolations, guidanceBody } from '@/test/utils'
import { speaker } from './speaker'
import { VoiceConversation } from './VoiceConversation'

const VOICES = [
  { lang: 'en-IN', name: 'English India' },
  { lang: 'bn-IN', name: 'Bengali India' },
  { lang: 'hi-IN', name: 'Hindi India' },
]

const hindiAnswer: Answer = {
  ...answerBody,
  language: 'hi',
  text: 'पारिवारिक आय 2,50,000 रुपये से अधिक नहीं होनी चाहिए।',
  claims: [{ text: 'पारिवारिक आय 2,50,000 रुपये से अधिक नहीं होनी चाहिए।', citations: [1] }],
  disclaimer: 'यह केवल जानकारी के लिए सारांश है।',
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  resetSpeaker()
  speaker.setRate('normal')
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

/** An `onAsk` the test settles by hand, like the server would. */
function server() {
  const asked: AskRequest[] = []
  const settlers: ((state: TurnState | null) => void)[] = []
  const onAsk = vi.fn((request: AskRequest) => {
    asked.push(request)
    return new Promise<TurnState | null>((resolve) => settlers.push(resolve))
  })
  return {
    asked,
    onAsk,
    answer: (answer: Answer = answerBody) =>
      act(async () => settlers.shift()?.({ status: 'done', answer })),
    fail: () => act(async () => settlers.shift()?.({ status: 'error', error: new Error('x') })),
    cancel: () => act(async () => settlers.shift()?.(null)),
  }
}

function panel(
  props: Partial<React.ComponentProps<typeof VoiceConversation>> = {},
  api = server(),
) {
  const view = render(
    <VoiceConversation
      uiLanguage="en"
      answerChoice="auto"
      onAsk={api.onAsk}
      busy={false}
      {...props}
    />,
  )
  return { ...view, api }
}

const talk = () => userEvent.click(screen.getByRole('button', { name: 'Start talking' }))
const status = () => screen.getByRole('status')

/** The prompt (or answer) is read to the end, sentence after sentence. */
const endSpeech = (speech: ReturnType<typeof installSpeech>) => act(() => speech.finishAll())

/** Everything said after the opening prompt, as one text. */
const saidAfterPrompt = (speech: ReturnType<typeof installSpeech>) =>
  speech
    .spoken()
    .slice(1)
    .map((piece) => piece.text)
    .join(' ')

describe('a conversation', () => {
  it('says what to do, listens, asks, reads the answer aloud and listens again', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()

    await talk()
    expect(speech.spoken()[0]).toMatchObject({
      text: 'Hello! What would you like to know about government schemes or your rights?',
      voice: 'English India',
    })
    expect(status()).toHaveTextContent(
      'Hello! What would you like to know about government schemes or your rights?',
    )
    expect(recognition.all()).toHaveLength(0) // it does not listen to its own voice
    endSpeech(speech)

    expect(recognition.last()?.started).toBe(true)
    expect(recognition.last()?.lang).toBe('en-IN')
    expect(status()).toHaveTextContent('Listening… ask your question.')
    act(() => recognition.last()!.hear('what is the income limit'))
    expect(screen.getByText('what is the income limit')).toBeVisible() // shown as it is heard
    expect(status()).not.toHaveTextContent('income limit') // but not announced word by word
    act(() => recognition.last()!.stop()) // the speaker paused: recognition ends by itself

    expect(api.asked).toEqual([{ question: 'what is the income limit', language: 'en' }])
    expect(status()).toHaveTextContent('Looking in the official documents…')
    await api.answer()

    expect(status()).toHaveTextContent('Reading the answer…')
    endSpeech(speech) // read through, sentence after sentence
    // Said like a person would: a lead-in, the answer, the disclaimer, and an invitation to ask more.
    const saidAloud = saidAfterPrompt(speech)
    expect(saidAloud.startsWith('Here is what the official documents say.')).toBe(true)
    expect(saidAloud).toContain("Your family's yearly income must not be more than Rs 2,50,000.")
    expect(saidAloud).toContain('Check the official document before acting.')
    expect(saidAloud.endsWith('Is there anything else you would like to ask?')).toBe(true)

    expect(recognition.all()).toHaveLength(2) // listening again for the next question
    expect(status()).toHaveTextContent('Listening… ask your question.')
    expect(screen.getByRole('button', { name: 'Stop talking' })).toBeVisible()
  })

  it('can go on question after question', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    await talk()
    for (const question of ['first question', 'second question']) {
      endSpeech(speech)
      act(() => recognition.last()!.hear(question))
      act(() => recognition.last()!.stop())
      await api.answer()
    }

    expect(api.asked.map((request) => request.question)).toEqual([
      'first question',
      'second question',
    ])
  })

  it('stops when asked to, whatever it is doing, and starts clean the next time', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    await talk()
    endSpeech(speech)

    await userEvent.click(screen.getByRole('button', { name: 'Stop talking' }))

    expect(recognition.last()?.aborted).toBe(true)
    expect(screen.getByRole('button', { name: 'Start talking' })).toBeVisible()
    expect(api.asked).toEqual([])
    await talk() // a new session begins with the prompt again
    expect(
      speech.spoken().filter((piece) => piece.text.startsWith('Hello! What would you like')),
    ).toHaveLength(2)
  })

  it('ignores an answer that arrives after the person stopped', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.hear('a question'))
    act(() => recognition.last()!.stop())

    await userEvent.click(screen.getByRole('button', { name: 'Stop talking' }))
    await api.answer()

    expect(speech.spoken()).toHaveLength(1) // only the prompt: the late answer was not read
    expect(screen.getByRole('button', { name: 'Start talking' })).toBeVisible()
  })

  it('stops reading and listening when the page is left', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { unmount, api } = panel()
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.hear('a question'))
    act(() => recognition.last()!.stop())
    await api.answer()
    expect(speaker.getSnapshot().playingId).toMatch(/^voice-answer/)

    unmount()

    expect(speaker.getSnapshot().playingId).toBeNull()
    expect(recognition.last()?.aborted).toBeFalsy() // it had ended; nothing is left to abort
  })

  it('does not start while a typed question is waiting', () => {
    installSpeech(VOICES)
    installRecognition()
    panel({ busy: true })

    expect(screen.getByRole('button', { name: 'Start talking' })).toBeDisabled()
  })
})

describe('what the panel shows', () => {
  const chip = (word: string) => screen.getByText(word, { selector: 'span' })

  it('names the state in a word that follows the conversation', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    expect(chip('Ready')).toBeVisible()

    await talk()
    expect(chip('Speaking')).toBeVisible() // the prompt
    endSpeech(speech)
    expect(chip('Listening')).toBeVisible()
    act(() => recognition.last()!.hear('a question'))
    act(() => recognition.last()!.stop())
    expect(chip('Thinking')).toBeVisible()
    await api.answer()
    expect(chip('Speaking')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Stop talking' }))

    expect(chip('Ready')).toBeVisible()
  })

  it('says it is stopped, in a word, when it stopped by itself', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    panel()
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.stop())
    act(() => recognition.last()!.stop())

    expect(chip('Stopped')).toBeVisible()
  })

  it('shows where in the round it is, and hides the decoration from a screen reader', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { container, api } = panel()
    expect(container.querySelector('ol')).toBeNull() // nothing to follow before it starts

    await talk()
    endSpeech(speech)
    const steps = container.querySelector('ol')!
    expect(steps).toHaveAttribute('aria-hidden', 'true')
    expect(steps).toHaveTextContent('1Listen2Look up3Answer')
    act(() => recognition.last()!.hear('a question'))
    act(() => recognition.last()!.stop())
    await api.answer()

    expect(steps).toHaveTextContent('\u{2713}Listen\u{2713}Look up3Answer')
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(3)
  })

  it('marks the chosen language with a tick as well as a color', () => {
    installSpeech(VOICES)
    installRecognition()
    panel()

    const english = screen.getByRole('button', { name: 'English' })
    const bengali = screen.getByRole('button', { name: 'বাংলা' })

    expect(english).toHaveAttribute('aria-pressed', 'true')
    expect(english.querySelector('svg')).not.toBeNull()
    expect(bengali.querySelector('svg')).toBeNull()
  })
})

describe('talking like a person', () => {
  it('reads general help after the words that say it is not from a document, then asks', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.hear('how do I get a pension'))
    act(() => recognition.last()!.stop())
    await api.answer(guidanceBody)
    endSpeech(speech)

    const saidAloud = saidAfterPrompt(speech)
    expect(saidAloud.startsWith('I could not find this in the official documents')).toBe(true)
    expect(saidAloud).toContain('Keep your identity proof and your bank passbook ready.')
    expect(saidAloud.endsWith('Which state do you live in?')).toBe(true)
    expect(recognition.all()).toHaveLength(2) // and then it listens for the reply
  })

  it('reads the disclaimer after the first answer only; it stays on the screen', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    await talk()
    const spokenAnswers: string[] = []
    for (const question of ['first question', 'second question']) {
      endSpeech(speech)
      act(() => recognition.last()!.hear(question))
      act(() => recognition.last()!.stop())
      const before = speech.spoken().length
      await api.answer()
      endSpeech(speech)
      spokenAnswers.push(
        speech
          .spoken()
          .slice(before)
          .map((piece) => piece.text)
          .join(' '),
      )
    }

    expect(spokenAnswers[0]).toContain('not legal advice')
    expect(spokenAnswers[1]).not.toContain('not legal advice')
    expect(spokenAnswers[1]).toContain('Rs 2,50,000')
  })

  it('reads the disclaimer again in a new conversation', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    for (let round = 0; round < 2; round += 1) {
      await talk()
      endSpeech(speech)
      act(() => recognition.last()!.hear('a question'))
      act(() => recognition.last()!.stop())
      await api.answer()
      endSpeech(speech)
      await userEvent.click(screen.getByRole('button', { name: 'Stop talking' }))
    }

    expect(speech.spoken().filter((piece) => piece.text.includes('not legal advice'))).toHaveLength(
      2,
    )
  })
})

describe('tapping a question instead of speaking one', () => {
  const PRAGATI = 'Who can apply for the AICTE Pragati scholarship?'

  it('offers questions in the language to be spoken, and only while it is not running', async () => {
    installSpeech(VOICES)
    installRecognition()
    panel()
    expect(screen.getByRole('button', { name: PRAGATI })).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: 'हिन्दी' }))
    expect(
      screen.getByRole('button', { name: 'AICTE प्रगति छात्रवृत्ति के लिए कौन आवेदन कर सकता है?' }),
    ).toBeVisible()
    await talk()

    expect(screen.queryByRole('list')).toBeNull()
  })

  it('asks it at once, reads the answer, and then listens for the next question', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()

    await userEvent.click(screen.getByRole('button', { name: PRAGATI }))

    expect(api.asked).toEqual([{ question: PRAGATI, language: 'en' }])
    expect(speech.spoken()).toEqual([]) // no prompt: the question is already there
    expect(screen.getByText(PRAGATI, { selector: 'p' })).toBeVisible()
    await api.answer()
    expect(speech.spoken()[0]?.text).toContain('Rs 2,50,000')
    endSpeech(speech)

    expect(recognition.last()?.started).toBe(true)
    expect(screen.getByRole('button', { name: 'Stop talking' })).toBeVisible()
  })

  it('cannot be used while a typed question is waiting', () => {
    installSpeech(VOICES)
    installRecognition()
    panel({ busy: true })

    expect(screen.getByRole('button', { name: PRAGATI })).toBeDisabled()
  })

  it('offers nothing to tap when the device cannot talk', () => {
    installSpeech(VOICES) // no recognition
    panel()

    expect(screen.queryByRole('list')).toBeNull()
  })
})

describe('languages', () => {
  it.each([
    [
      'en',
      'Start talking',
      'en-IN',
      'Hello! What would you like to know about government schemes or your rights?',
      'English India',
    ],
    [
      'bn',
      'কথা শুরু করুন',
      'bn-IN',
      'নমস্কার! সরকারি প্রকল্প বা আপনার অধিকার নিয়ে আপনি কী জানতে চান?',
      'Bengali India',
    ],
    [
      'hi',
      'बात शुरू करें',
      'hi-IN',
      'नमस्ते! सरकारी योजनाओं या आपके अधिकारों के बारे में आप क्या जानना चाहेंगे?',
      'Hindi India',
    ],
  ] as const)(
    'in %s: prompts, listens and answers in that language',
    async (language, button, tag, prompt, voice) => {
      const speech = installSpeech(VOICES)
      const recognition = installRecognition()
      const { api } = panel({ uiLanguage: language })

      await userEvent.click(screen.getByRole('button', { name: button }))
      expect(speech.spoken()[0]).toMatchObject({ text: prompt, voice })
      endSpeech(speech)
      expect(recognition.last()?.lang).toBe(tag)
      act(() => recognition.last()!.hear('x'))
      act(() => recognition.last()!.stop())

      expect(api.asked[0]?.language).toBe(language)
    },
  )

  it('lets the person speak in one language and keeps that language for the answer', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()

    await userEvent.click(screen.getByRole('button', { name: 'हिन्दी' }))
    await talk()
    expect(speech.spoken()[0]).toMatchObject({ voice: 'Hindi India' }) // the prompt, in Hindi
    endSpeech(speech)
    expect(recognition.last()?.lang).toBe('hi-IN')
    act(() => recognition.last()!.hear('आय की सीमा क्या है'))
    act(() => recognition.last()!.stop())
    expect(api.asked[0]).toEqual({ question: 'आय की सीमा क्या है', language: 'hi' })
    await api.answer(hindiAnswer)

    expect(speech.spoken().at(-1)).toMatchObject({ voice: 'Hindi India', lang: 'hi-IN' })
    expect(speech.spoken().at(-1)?.text).toContain('पारिवारिक आय 2,50,000 रुपये')
  })

  it('answers in the language of the answer box when it is not automatic', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel({ answerChoice: 'bn' })
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.hear('what is the limit'))
    act(() => recognition.last()!.stop())

    expect(api.asked[0]?.language).toBe('bn') // spoken in English, answered in Bengali
  })

  it('keeps the language chosen for the answer from a scheme and passes the scheme on', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel({ sourceIds: ['wb-svmcm-guidelines'] })
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.hear('a question'))
    act(() => recognition.last()!.stop())

    expect(api.asked[0]).toEqual({
      question: 'a question',
      language: 'en',
      source_ids: ['wb-svmcm-guidelines'],
    })
  })

  it('cannot change the spoken language in the middle of a conversation', async () => {
    installSpeech(VOICES)
    installRecognition()
    panel()
    await talk()

    expect(screen.getByRole('button', { name: 'हिन्दी' })).toBeDisabled()
  })

  it('names each language in its own script', () => {
    installSpeech(VOICES)
    installRecognition()
    panel({ uiLanguage: 'hi' })

    expect(
      screen
        .getAllByRole('button', { pressed: undefined })
        .slice(0, 3)
        .map((b) => b.textContent),
    ).toEqual(['English', 'বাংলা', 'हिन्दी'])
  })
})

describe('when something goes wrong, it says so aloud and on the screen', () => {
  it('says that no answer could be found, and stops', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.hear('a question'))
    act(() => recognition.last()!.stop())

    await api.fail()

    expect(speech.spoken().at(-1)?.text).toBe('Sorry, I could not get an answer. Please try again.')
    endSpeech(speech)
    expect(status()).toHaveTextContent('Stopped: the answer could not be found.')
    expect(screen.getByRole('button', { name: 'Start talking' })).toBeVisible()
    expect(recognition.all()).toHaveLength(1) // it does not listen again after a failure
  })

  it('stops after two silences in a row, not after one', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    panel()
    await talk()
    endSpeech(speech)

    act(() => recognition.last()!.stop()) // nothing was said
    expect(recognition.all()).toHaveLength(2) // it listens once more
    expect(status()).toHaveTextContent('Listening…')
    act(() => recognition.last()!.stop())

    expect(status()).toHaveTextContent('I did not hear anything, so I stopped.')
    expect(recognition.all()).toHaveLength(2)
  })

  it('counts a heard question as the end of the silences', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.stop()) // silence 1
    act(() => recognition.last()!.hear('a question'))
    act(() => recognition.last()!.stop())
    await api.answer()
    endSpeech(speech)

    act(() => recognition.last()!.stop()) // silence 1 again, not 2

    expect(status()).toHaveTextContent('Listening…')
  })

  it.each([
    ['not-allowed', 'The microphone is blocked'],
    ['network', 'needs an internet connection'],
    ['language-not-supported', 'cannot understand English speech'],
  ])('stops and says why when listening fails with "%s"', async (code, message) => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    panel()
    await talk()
    endSpeech(speech)

    act(() => recognition.last()!.fail(code))

    expect(status()).toHaveTextContent(message)
    expect(recognition.all()).toHaveLength(1) // it does not try again by itself
  })

  it('treats "no speech" as silence, not as a failure', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    panel()
    await talk()
    endSpeech(speech)

    act(() => recognition.last()!.fail('no-speech'))

    expect(recognition.all()).toHaveLength(2)
    expect(status()).toHaveTextContent('Listening…')
  })

  it('stops, and says the answer is on the screen, when it has no voice for the answer language', async () => {
    const speech = installSpeech(VOICES.filter((voice) => voice.lang !== 'hi-IN'))
    const recognition = installRecognition()
    const { api } = panel()
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.hear('a question'))
    act(() => recognition.last()!.stop())

    await api.answer(hindiAnswer)

    expect(status()).toHaveTextContent('this device has no voice for the language of the answer')
    expect(screen.getByRole('button', { name: 'Start talking' })).toBeVisible()
  })

  it('offers no start when the device has no voice for the language spoken', async () => {
    // Only a Hindi voice exists, but English is spoken: the panel offers no start at all.
    installSpeech([{ lang: 'hi-IN', name: 'Hindi India' }])
    installRecognition()
    panel()

    expect(screen.queryByRole('button', { name: 'Start talking' })).toBeNull()
    expect(screen.getByText(/no English voice/)).toBeVisible()
  })

  it('offers no talking in a browser that cannot recognise speech', () => {
    installSpeech(VOICES)
    panel()

    expect(screen.queryByRole('button', { name: 'Start talking' })).toBeNull()
    expect(screen.getByText(/needs speech recognition/)).toBeVisible()
  })

  it('offers no talking in a browser that cannot speak', () => {
    installRecognition()
    panel()

    expect(screen.queryByRole('button', { name: 'Start talking' })).toBeNull()
    expect(screen.getByText(/cannot read text aloud/)).toBeVisible()
  })

  it('ignores a cancelled question', async () => {
    const speech = installSpeech(VOICES)
    const recognition = installRecognition()
    const { api } = panel()
    await talk()
    endSpeech(speech)
    act(() => recognition.last()!.hear('a question'))
    act(() => recognition.last()!.stop())

    await api.cancel()

    expect(speech.spoken()).toHaveLength(1)
    expect(status()).toHaveTextContent('Looking in the official documents…')
  })
})

describe('for people who cannot see the screen', () => {
  it('keeps every step in one live region, so each is announced', async () => {
    const speech = installSpeech(VOICES)
    installRecognition()
    panel()

    await talk()
    endSpeech(speech)

    await waitFor(() => expect(status()).toHaveTextContent('Listening…'))
    expect(screen.getAllByRole('status')).toHaveLength(1)
  })

  it('has no automatically detectable accessibility problems, and big enough targets', async () => {
    installSpeech(VOICES)
    installRecognition()
    const { container } = panel()

    await expectNoAxeViolations(container)
    for (const button of screen.getAllByRole('button')) expect(button.className).toMatch(/min-h-12/)
  })
})
