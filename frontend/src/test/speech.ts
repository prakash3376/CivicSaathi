import { vi } from 'vitest'
import type {
  Recognition,
  RecognitionErrorEvent,
  RecognitionResultEvent,
} from '@/features/voice/dictation'
import { speaker } from '@/features/voice/speaker'

interface FakeVoice {
  lang: string
  name: string
}

export interface SpokenPiece {
  text: string
  lang: string
  rate: number
  voice: string | null
}

/**
 * A speech synthesis that speaks nothing but records what it was asked to say. `finishPiece()`
 * plays the browser's "end" event for the piece being spoken.
 */
export function installSpeech(voices: FakeVoice[]) {
  const asked: FakeUtterance[] = []
  const listeners = new Map<string, Set<() => void>>()
  let current: FakeUtterance | null = null

  class FakeUtterance {
    text: string
    lang = ''
    rate = 1
    voice: FakeVoice | null = null
    onend: (() => void) | null = null
    onerror: (() => void) | null = null
    constructor(text: string) {
      this.text = text
    }
  }

  const synthesis = {
    voices,
    getVoices: () => synthesis.voices,
    speak: vi.fn((utterance: FakeUtterance) => {
      asked.push(utterance)
      current = utterance
    }),
    cancel: vi.fn(() => {
      const interrupted = current
      current = null
      interrupted?.onerror?.() // a real browser reports "interrupted"
    }),
    addEventListener: (type: string, listener: () => void) => {
      if (!listeners.has(type)) listeners.set(type, new Set())
      listeners.get(type)?.add(listener)
    },
    removeEventListener: (type: string, listener: () => void) =>
      listeners.get(type)?.delete(listener),
  }
  vi.stubGlobal('speechSynthesis', synthesis)
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)

  return {
    synthesis,
    /** Every piece the page asked to speak, in order. */
    spoken: (): SpokenPiece[] =>
      asked.map((u) => ({
        text: u.text,
        lang: u.lang,
        rate: u.rate,
        voice: u.voice?.name ?? null,
      })),
    /** The piece being spoken ends, as the browser says. */
    finishPiece: () => {
      const finished = current
      current = null
      finished?.onend?.()
    },
    /** Every piece still to be spoken ends, one after another, as when a text is read through. */
    finishAll: () => {
      for (let guard = 0; current !== null && guard < 100; guard += 1) {
        const finished: FakeUtterance = current
        current = null
        finished.onend?.()
      }
    },
    /** The browser has loaded its voices. */
    loadVoices: (loaded: FakeVoice[]) => {
      synthesis.voices = loaded
      for (const listener of listeners.get('voiceschanged') ?? []) listener()
    },
  }
}

/** A speech recogniser that hears what the test says. */
export function installRecognition() {
  const sessions: FakeRecognition[] = []

  class FakeRecognition implements Recognition {
    lang = ''
    interimResults = false
    continuous = false
    onresult: ((event: RecognitionResultEvent) => void) | null = null
    onerror: ((event: RecognitionErrorEvent) => void) | null = null
    onend: (() => void) | null = null
    started = false
    aborted = false
    constructor() {
      sessions.push(this)
    }
    start() {
      this.started = true
    }
    stop() {
      this.onend?.()
    }
    abort() {
      this.aborted = true
    }
    /** The words heard so far (each item is one recognised phrase). */
    hear(...phrases: string[]) {
      this.onresult?.({ results: phrases.map((transcript) => [{ transcript }]) })
    }
    fail(code: string) {
      this.onerror?.({ error: code })
      this.onend?.()
    }
  }

  vi.stubGlobal('SpeechRecognition', FakeRecognition)
  return { last: () => sessions[sessions.length - 1], all: () => sessions }
}

/** Put the shared speaker back as it was: nothing playing. */
export function resetSpeaker() {
  speaker.stop()
}
