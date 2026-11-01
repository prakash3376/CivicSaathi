import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { installSpeech, resetSpeaker } from '@/test/speech'
import { expectNoAxeViolations } from '@/test/utils'
import { ListenControl } from './ListenControl'
import { speaker } from './speaker'

const ENGLISH_ONLY = [{ lang: 'en-IN', name: 'English India' }]
const ALL = [
  { lang: 'en-IN', name: 'English India' },
  { lang: 'bn-IN', name: 'Bengali India' },
  { lang: 'hi-IN', name: 'Hindi India' },
]

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  resetSpeaker()
  speaker.setRate('normal')
  vi.unstubAllGlobals()
})

function control(props: Partial<React.ComponentProps<typeof ListenControl>> = {}) {
  return (
    <ListenControl
      id="a"
      text="Income must be at most Rs 2,50,000."
      language="en"
      label="listenAnswer"
      uiLanguage="en"
      {...props}
    />
  )
}

describe('listening', () => {
  it('reads the text aloud when pressed, and stops when pressed again', async () => {
    const speech = installSpeech(ALL)
    render(control())

    await userEvent.click(screen.getByRole('button', { name: 'Listen to this answer' }))

    expect(speech.spoken()[0]).toMatchObject({
      text: 'Income must be at most Rs 2,50,000.',
      voice: 'English India',
    })
    const stop = screen.getByRole('button', { name: 'Stop reading' })
    await userEvent.click(stop)

    expect(screen.getByRole('button', { name: 'Listen to this answer' })).toBeVisible()
    expect(speaker.getSnapshot().playingId).toBeNull()
  })

  it('goes back to "Listen" by itself when the reading ends', async () => {
    const speech = installSpeech(ALL)
    render(control())
    await userEvent.click(screen.getByRole('button', { name: 'Listen to this answer' }))

    act(() => speech.finishPiece())

    expect(screen.getByRole('button', { name: 'Listen to this answer' })).toBeVisible()
  })

  it('shows "Stop" only on the one being read', async () => {
    installSpeech(ALL)
    render(
      <>
        {control({ id: 'one' })}
        {control({ id: 'two', label: 'listenResult' })}
      </>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Listen to this answer' }))

    expect(screen.getAllByRole('button', { name: 'Stop reading' })).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Listen to this result' })).toBeVisible()
  })

  it('stops reading when the page is left', async () => {
    installSpeech(ALL)
    const { unmount } = render(control())
    await userEvent.click(screen.getByRole('button', { name: 'Listen to this answer' }))

    unmount()

    expect(speaker.getSnapshot().playingId).toBeNull()
  })

  it('does not stop a reading that is not its own when it goes away', async () => {
    installSpeech(ALL)
    const other = render(control({ id: 'other' }))
    const mine = render(control({ id: 'mine' }))
    await userEvent.click(within(other.container).getByRole('button'))

    mine.unmount()

    expect(speaker.getSnapshot().playingId).toBe('other')
  })
})

describe('speed', () => {
  it('offers three speeds, reads at the chosen one, and remembers it', async () => {
    const speech = installSpeech(ALL)
    render(control())

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Reading speed' }), 'Slower')
    await userEvent.click(screen.getByRole('button', { name: 'Listen to this answer' }))

    expect(speech.spoken()[0]?.rate).toBe(0.8)
    expect(localStorage.getItem('civicsaathi.speech-rate')).toBe('slow')
    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual([
      'Slower',
      'Normal',
      'Faster',
    ])
  })
})

describe('when it cannot read', () => {
  it('says so when the device has no voice for the language, and offers no button', () => {
    installSpeech(ENGLISH_ONLY)
    render(control({ language: 'bn', text: 'এটি একটি বাক্য।' }))

    expect(screen.getByText(/no Bengali voice/)).toBeVisible()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('says the same for Hindi, in Hindi when the page is in Hindi', () => {
    installSpeech(ENGLISH_ONLY)
    render(control({ language: 'hi', uiLanguage: 'hi', text: 'यह एक वाक्य है।' }))

    expect(screen.getByText(/हिन्दी भाषा की आवाज़ नहीं है/)).toBeVisible()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('says so when the browser cannot read aloud at all', () => {
    render(control())

    expect(screen.getByText(/cannot read text aloud/)).toBeVisible()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('waits for the browser to load its voices before deciding', async () => {
    const speech = installSpeech([])
    render(control({ language: 'hi', text: 'यह एक वाक्य है।' }))

    expect(screen.getByRole('button', { name: 'Listen to this answer' })).toBeVisible()
    act(() => speech.loadVoices(ALL))

    expect(screen.getByRole('button', { name: 'Listen to this answer' })).toBeVisible()
  })

  it('gives up waiting, and says there is no voice, if none ever loads', () => {
    vi.useFakeTimers()
    installSpeech([])
    render(control())

    act(() => {
      vi.advanceTimersByTime(2500)
    })

    expect(screen.getByText(/no English voice/)).toBeVisible()
    vi.useRealTimers()
  })

  it('says so when voices load and none is for the language', () => {
    const speech = installSpeech([])
    render(control({ language: 'bn', text: 'এটি একটি বাক্য।' }))

    act(() => speech.loadVoices(ENGLISH_ONLY))

    expect(screen.getByText(/no Bengali voice/)).toBeVisible()
  })
})

describe('in each language', () => {
  it.each([
    ['en', 'Listen to this answer', 'Reading speed'],
    ['bn', 'এই উত্তরটি শুনুন', 'পড়ার গতি'],
    ['hi', 'यह उत्तर सुनें', 'पढ़ने की गति'],
  ] as const)('speaks its own words in %s', (uiLanguage, button, speed) => {
    installSpeech(ALL)
    render(control({ uiLanguage }))

    expect(screen.getByRole('button', { name: button })).toBeVisible()
    expect(screen.getByRole('combobox', { name: speed })).toBeVisible()
  })

  it('has no automatically detectable accessibility problems, and big enough targets', async () => {
    installSpeech(ALL)
    const { container } = render(control())

    await expectNoAxeViolations(container)
    for (const element of [screen.getByRole('button'), screen.getByRole('combobox')]) {
      expect(element.className).toMatch(/min-h-12/)
    }
  })
})
