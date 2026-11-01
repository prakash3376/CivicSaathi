import type { DictationProblem } from './dictation'
import type { VoiceKey } from './strings'

/** The words for each way listening can fail. */
export const PROBLEM_TEXT: Record<DictationProblem, VoiceKey> = {
  denied: 'micDenied',
  no_speech: 'micNoSpeech',
  network: 'micNetwork',
  language: 'micLanguage',
  busy: 'micBusy',
  failed: 'micFailed',
}
