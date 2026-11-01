/**
 * Reading text aloud with the browser's own speech synthesis. Nothing is sent to CivicSaathi's
 * server: the voice runs on the device (or the browser's own service), and what is read is text the
 * page already shows.
 *
 * Only one thing is read at a time, because the browser has one speaker. A text is cut into short
 * pieces and spoken one after another: Chrome stops a long utterance after about fifteen seconds.
 * A text is read only with a voice made for its language: an English voice reading Bengali is
 * noise, so without a Bengali voice the page says so instead (SPEC rule R8).
 */
import type { UiLanguage } from '@/i18n/translator'

/** Tags to look for, best first. English written for India comes first, as the users are there. */
const TAGS: Record<UiLanguage, readonly string[]> = {
  en: ['en-in', 'en-gb', 'en-us', 'en'],
  bn: ['bn-in', 'bn-bd', 'bn'],
  hi: ['hi-in', 'hi'],
}

const normalise = (tag: string) => tag.toLowerCase().replaceAll('_', '-')

/** The best voice for a language, or null if the device has none. */
export function pickVoice(
  voices: readonly SpeechSynthesisVoice[],
  language: UiLanguage,
): SpeechSynthesisVoice | null {
  for (const tag of TAGS[language]) {
    const exact = voices.find((voice) => normalise(voice.lang) === tag)
    if (exact) return exact
  }
  return voices.find((voice) => normalise(voice.lang).startsWith(`${language}-`)) ?? null
}

// A sentence ends at . ! ? or the Bengali danda, followed by a space or the end.
const SENTENCE_END = /(?<=[.!?\u{0964}])\s+/u

/**
 * The text cut into pieces of at most `max` characters, at sentence ends where possible, else at
 * a space, so that no piece is cut in the middle of a word.
 */
export function splitForSpeech(text: string, max = 180): string[] {
  const pieces: string[] = []
  let current = ''
  const flush = () => {
    if (current) pieces.push(current)
    current = ''
  }
  for (const sentence of text.replace(/\s+/g, ' ').trim().split(SENTENCE_END)) {
    if (!sentence) continue
    if (sentence.length > max) {
      flush()
      let rest = sentence
      while (rest.length > max) {
        const at = rest.lastIndexOf(' ', max)
        const cut = at > 0 ? at : max
        pieces.push(rest.slice(0, cut).trim())
        rest = rest.slice(cut).trim()
      }
      current = rest
    } else if (current && current.length + 1 + sentence.length > max) {
      flush()
      current = sentence
    } else {
      current = current ? `${current} ${sentence}` : sentence
    }
  }
  flush()
  return pieces
}

export const RATES = { slow: 0.8, normal: 1, fast: 1.25 } as const
export type RateName = keyof typeof RATES

const RATE_KEY = 'civicsaathi.speech-rate'

function isRateName(value: string | null): value is RateName {
  return value === 'slow' || value === 'normal' || value === 'fast'
}

function storedRate(): RateName {
  try {
    const stored = localStorage.getItem(RATE_KEY)
    return isRateName(stored) ? stored : 'normal'
  } catch {
    return 'normal' // storage can be blocked
  }
}

export interface SpeakerState {
  /** What is being read now (any id the caller chose), or null. */
  playingId: string | null
  /** How fast to read: the one preference of the voice controls, remembered between visits. */
  rate: RateName
}

type Listener = () => void

const synthesis = (): SpeechSynthesis | null =>
  typeof window !== 'undefined' &&
  'speechSynthesis' in window &&
  'SpeechSynthesisUtterance' in window
    ? window.speechSynthesis
    : null

class Speaker {
  private state: SpeakerState = { playingId: null, rate: storedRate() }
  private listeners = new Set<Listener>()
  private token = 0
  private ending: ((finished: boolean) => void) | null = null

  readonly subscribe = (listener: Listener) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  readonly getSnapshot = () => this.state

  private update(change: Partial<SpeakerState>) {
    this.state = { ...this.state, ...change }
    for (const listener of this.listeners) listener()
  }

  /** Tell whoever asked for the reading that is over how it ended (once). */
  private settle(finished: boolean) {
    const ending = this.ending
    this.ending = null
    ending?.(finished)
  }

  /** Applies from the next thing read, not to the sentence being spoken. */
  setRate(rate: RateName) {
    this.update({ rate })
    try {
      localStorage.setItem(RATE_KEY, rate)
    } catch {
      // Not remembered this time; reading still works.
    }
  }

  supported(): boolean {
    return synthesis() !== null
  }

  voices(): SpeechSynthesisVoice[] {
    return synthesis()?.getVoices() ?? []
  }

  /**
   * Read `text` in `language`. Returns false if the device has no voice for it. `onEnd` is told
   * once how the reading ended: true if it was read to the end, false if it was stopped, replaced
   * or failed.
   */
  speak(
    id: string,
    text: string,
    language: UiLanguage,
    onEnd?: (finished: boolean) => void,
  ): boolean {
    const engine = synthesis()
    const voice = pickVoice(this.voices(), language)
    const pieces = splitForSpeech(text)
    if (!engine || !voice || pieces.length === 0) return false

    engine.cancel() // the previous reading, if any
    this.settle(false)
    const mine = ++this.token
    this.ending = onEnd ?? null
    this.update({ playingId: id })

    const next = (index: number) => {
      if (mine !== this.token) return // stopped, or something else started
      const piece = pieces[index]
      if (piece === undefined) {
        this.update({ playingId: null })
        this.settle(true)
        return
      }
      const utterance = new SpeechSynthesisUtterance(piece)
      utterance.voice = voice
      utterance.lang = voice.lang
      utterance.rate = RATES[this.state.rate]
      // An error (including "interrupted" by our own cancel) ends this reading, not the next one.
      utterance.onend = () => next(index + 1)
      utterance.onerror = () => {
        if (mine !== this.token) return
        this.update({ playingId: null })
        this.settle(false)
      }
      engine.speak(utterance)
    }
    next(0)
    return true
  }

  stop() {
    this.token++
    synthesis()?.cancel()
    if (this.state.playingId !== null) this.update({ playingId: null })
    this.settle(false)
  }
}

/** The one speaker of the page. */
export const speaker = new Speaker()
