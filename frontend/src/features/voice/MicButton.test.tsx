import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { act } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { installRecognition } from '@/test/speech'
import { expectNoAxeViolations } from '@/test/utils'
import { MicButton } from './MicButton'
import { problemFrom, transcriptOf } from './dictation'

afterEach(() => {
  vi.unstubAllGlobals()
})

function mic(props: Partial<React.ComponentProps<typeof MicButton>> = {}) {
  const calls = { start: vi.fn(), text: vi.fn(), finish: vi.fn() }
  const view = render(
    <MicButton
      language="en"
      uiLanguage="en"
      onStart={calls.start}
      onText={calls.text}
      onFinish={calls.finish}
      {...props}
    />,
  )
  return { ...view, calls }
}

describe('speaking a question', () => {
  it('listens in the language asked, and hands over the words as they come', async () => {
    const recognition = installRecognition()
    const { calls } = mic({ language: 'hi', uiLanguage: 'hi' })

    await userEvent.click(screen.getByRole('button', { name: 'बोलकर प्रश्न पूछें' }))

    const session = recognition.last()!
    expect(session.started).toBe(true)
    expect(session.lang).toBe('hi-IN')
    expect(session.interimResults).toBe(true)
    expect(calls.start).toHaveBeenCalledOnce()
    expect(screen.getByRole('status')).toHaveTextContent('सुन रहे हैं')
    act(() => session.hear('आय की'))
    act(() => session.hear('आय की', 'सीमा क्या है'))
    expect(calls.text).toHaveBeenLastCalledWith('आय की सीमा क्या है')
  })

  it.each([
    ['en', 'en-IN'],
    ['bn', 'bn-IN'],
    ['hi', 'hi-IN'],
  ] as const)('asks the recogniser for %s as %s', async (language, tag) => {
    const recognition = installRecognition()
    mic({ language })

    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))

    expect(recognition.last()?.lang).toBe(tag)
  })

  it('stops on request, says what to do next, and tells the form it is over', async () => {
    const recognition = installRecognition()
    const { calls } = mic()
    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))
    act(() => recognition.last()!.hear('what is the income limit'))

    await userEvent.click(screen.getByRole('button', { name: 'Stop and use what I said' }))

    expect(calls.finish).toHaveBeenCalledWith(true)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Please check your question, then press Ask.',
    )
    expect(screen.getByRole('button', { name: 'Speak your question' })).toBeVisible()
  })

  it('does not claim to have heard anything when nothing was said', async () => {
    const recognition = installRecognition()
    const { calls } = mic()
    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))

    act(() => recognition.last()!.stop())

    expect(calls.finish).toHaveBeenCalledWith(false)
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('never sends anything by itself: it only hands over words', async () => {
    const recognition = installRecognition()
    const { calls } = mic()
    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))
    act(() => recognition.last()!.hear('hello'))

    expect(Object.keys(calls).sort()).toEqual(['finish', 'start', 'text'])
  })

  it('cuts the recognition off when the page is left', async () => {
    const recognition = installRecognition()
    const { unmount, calls } = mic()
    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))

    unmount()

    expect(recognition.last()?.aborted).toBe(true)
    expect(calls.finish).not.toHaveBeenCalled()
  })

  it('stops the speaker first, so it does not listen to its own voice', async () => {
    installRecognition()
    const { speaker } = await import('./speaker')
    const stop = vi.spyOn(speaker, 'stop')
    mic()

    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))

    expect(stop).toHaveBeenCalled()
  })

  it('cannot be started while a question is being answered', () => {
    installRecognition()
    mic({ disabled: true })

    expect(screen.getByRole('button', { name: 'Speak your question' })).toBeDisabled()
  })
})

describe('when it does not work', () => {
  it.each([
    ['not-allowed', 'The microphone is blocked'],
    ['service-not-allowed', 'The microphone is blocked'],
    ['no-speech', 'We did not hear anything'],
    ['network', 'needs an internet connection'],
    ['language-not-supported', 'cannot understand Bengali speech'],
    ['audio-capture', 'microphone could not be used'],
    ['something-new', 'did not work this time'],
  ])('says what went wrong for "%s", and offers typing', async (code, message) => {
    const recognition = installRecognition()
    mic({ language: 'bn' })
    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))

    act(() => recognition.last()!.fail(code))

    expect(screen.getByRole('status')).toHaveTextContent(message)
    expect(screen.getByRole('button', { name: 'Speak your question' })).toBeEnabled() // try again
  })

  it('does not report our own abort as a problem', () => {
    expect(problemFrom('aborted')).toBeNull()
  })

  it('says so, and offers typing, in a browser that cannot recognise speech', () => {
    mic()

    expect(screen.getByText(/cannot turn speech into text/)).toBeVisible()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('does not start twice if pressed again before the first has ended', async () => {
    const recognition = installRecognition()
    mic()

    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))
    await userEvent.click(screen.getByRole('button', { name: 'Stop and use what I said' }))
    await userEvent.click(screen.getByRole('button', { name: 'Speak your question' }))

    expect(recognition.all()).toHaveLength(2) // one session each, not two at once
  })
})

describe('what is said about the audio', () => {
  it.each([
    ['en', /may send the recording to its own speech service/],
    ['bn', /রেকর্ডিংটি তার নিজের কথা-বোঝার সেবায়/],
    ['hi', /रिकॉर्डिंग को अपनी भाषण-सेवा/],
  ] as const)('tells the person where the recording goes, in %s', (uiLanguage, words) => {
    installRecognition()
    mic({ uiLanguage })

    expect(screen.getByText(words)).toBeVisible()
  })

  it('has no automatically detectable accessibility problems, and a big enough target', async () => {
    installRecognition()
    const { container } = mic()

    await expectNoAxeViolations(container)
    expect(screen.getByRole('button').className).toMatch(/min-h-12/)
  })
})

describe('reading what the recogniser gives', () => {
  it('joins the phrases and tidies the spaces', () => {
    expect(
      transcriptOf({ results: [[{ transcript: ' what is ' }], [{ transcript: 'the limit ' }]] }),
    ).toBe('what is the limit')
  })

  it('copes with a phrase that has no alternative', () => {
    expect(transcriptOf({ results: [[], [{ transcript: 'hello' }]] })).toBe('hello')
  })
})
