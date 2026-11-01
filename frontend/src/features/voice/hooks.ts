import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import type { UiLanguage } from '@/i18n/translator'
import {
  problemFrom,
  recognitionConstructor,
  RECOGNITION_LANG,
  transcriptOf,
  type DictationProblem,
  type Recognition,
} from './dictation'
import { pickVoice, speaker } from './speaker'
import { translator } from './strings'

/** The voice controls' words in the language of the interface. */
export function useVoiceText(uiLanguage: UiLanguage) {
  return useMemo(() => translator(uiLanguage), [uiLanguage])
}

/** What the speaker is doing, and the reading speed. Re-renders when either changes. */
export function useSpeaker() {
  return useSyncExternalStore(speaker.subscribe, speaker.getSnapshot)
}

const VOICE_WAIT_MS = 2000

export type VoiceAvailability = 'unsupported' | 'checking' | 'ready' | 'missing'

/**
 * Whether the device can read this language aloud. Browsers load their voices late (Chrome says so
 * with `voiceschanged`), so for a moment the answer is "checking" rather than "missing".
 */
export function useVoiceAvailability(language: UiLanguage): VoiceAvailability {
  const [, refresh] = useState(0)
  const [waited, setWaited] = useState(false)
  const supported = speaker.supported()

  useEffect(() => {
    if (!supported) return
    const engine = window.speechSynthesis
    const onChange = () => refresh((count) => count + 1)
    engine.addEventListener('voiceschanged', onChange)
    const timer = setTimeout(() => setWaited(true), VOICE_WAIT_MS)
    return () => {
      engine.removeEventListener('voiceschanged', onChange)
      clearTimeout(timer)
    }
  }, [supported])

  if (!supported) return 'unsupported'
  const voices = speaker.voices()
  if (voices.length > 0) return pickVoice(voices, language) ? 'ready' : 'missing'
  return waited ? 'missing' : 'checking'
}

interface DictationOptions {
  /** The words recognised so far, as they grow. */
  onText: (text: string) => void
  /** Recognition ended; `heard` says whether anything was recognised, `problem` why it failed. */
  onFinish: (heard: boolean, problem: DictationProblem | null) => void
}

/** Speaking a question: start, stop, and why it stopped if something went wrong. */
export function useDictation(language: UiLanguage, { onText, onFinish }: DictationOptions) {
  const [listening, setListening] = useState(false)
  const [problem, setProblem] = useState<DictationProblem | null>(null)
  const recognition = useRef<Recognition | null>(null)
  const heard = useRef(false)
  const failure = useRef<DictationProblem | null>(null)
  const callbacks = useRef({ onText, onFinish })
  useEffect(() => {
    callbacks.current = { onText, onFinish }
  })
  const Recognizer = recognitionConstructor()

  const start = useCallback(() => {
    const Constructor = recognitionConstructor()
    if (!Constructor || recognition.current) return
    speaker.stop() // do not listen to our own voice
    const session = new Constructor()
    session.lang = RECOGNITION_LANG[language]
    session.interimResults = true
    session.continuous = false
    heard.current = false
    failure.current = null
    setProblem(null)
    session.onresult = (event) => {
      const text = transcriptOf(event)
      if (text) heard.current = true
      callbacks.current.onText(text)
    }
    session.onerror = (event) => {
      failure.current = problemFrom(event.error)
      setProblem(failure.current)
    }
    session.onend = () => {
      recognition.current = null
      setListening(false)
      callbacks.current.onFinish(heard.current, failure.current)
    }
    recognition.current = session
    try {
      session.start()
      setListening(true)
    } catch {
      recognition.current = null
      setProblem('failed')
      callbacks.current.onFinish(false, 'failed')
    }
  }, [language])

  const stop = useCallback(() => recognition.current?.stop(), [])

  /** Stop at once and report nothing: the person (or the page) walked away. */
  const cancel = useCallback(() => {
    const session = recognition.current
    if (!session) return
    session.onresult = session.onerror = session.onend = null
    session.abort()
    recognition.current = null
    setListening(false)
  }, [])

  useEffect(
    () => () => {
      const session = recognition.current
      if (session) {
        session.onresult = session.onerror = session.onend = null
        session.abort()
        recognition.current = null
      }
    },
    [],
  )

  return { supported: Recognizer !== null, listening, problem, start, stop, cancel }
}
