/**
 * Speaking a question instead of typing it, with the browser's own speech recognition.
 *
 * Be clear about where the audio goes: in Chrome and Edge the recording is sent to the browser
 * maker's speech service (Google, Microsoft) to be turned into text; CivicSaathi never receives
 * it. The page says so next to the microphone. The recognised text lands in the question box for
 * the person to check and edit: it is never sent on its own.
 */
import type { UiLanguage } from '@/i18n/translator'

// The DOM typings of TypeScript do not include speech recognition: these are the parts used.
interface RecognitionAlternative {
  transcript: string
}
interface RecognitionResult {
  readonly length: number
  [index: number]: RecognitionAlternative | undefined
}
export interface RecognitionResultEvent {
  results: ArrayLike<RecognitionResult>
}
export interface RecognitionErrorEvent {
  error: string
}
export interface Recognition {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: RecognitionResultEvent) => void) | null
  onerror: ((event: RecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}
type RecognitionConstructor = new () => Recognition

/** The tag to ask the recogniser for. India's variants, as the users are there. */
export const RECOGNITION_LANG: Record<UiLanguage, string> = {
  en: 'en-IN',
  bn: 'bn-IN',
  hi: 'hi-IN',
}

export function recognitionConstructor(): RecognitionConstructor | null {
  if (typeof window === 'undefined') return null
  const found = window as unknown as {
    SpeechRecognition?: RecognitionConstructor
    webkitSpeechRecognition?: RecognitionConstructor
  }
  return found.SpeechRecognition ?? found.webkitSpeechRecognition ?? null
}

export type DictationProblem = 'denied' | 'no_speech' | 'network' | 'language' | 'busy' | 'failed'

/** Why recognition stopped, from the browser's error code. `aborted` is our own doing: no problem. */
export function problemFrom(code: string): DictationProblem | null {
  switch (code) {
    case 'aborted':
      return null
    case 'not-allowed':
    case 'service-not-allowed':
      return 'denied'
    case 'no-speech':
      return 'no_speech'
    case 'network':
      return 'network'
    case 'language-not-supported':
      return 'language'
    case 'audio-capture':
      return 'busy'
    default:
      return 'failed'
  }
}

/** All the words recognised so far, in order. */
export function transcriptOf(event: RecognitionResultEvent): string {
  return Array.from(event.results, (result) => result[0]?.transcript ?? '')
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
}
