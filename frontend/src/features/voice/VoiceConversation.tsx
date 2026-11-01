import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { AskRequest, LanguageChoice, SectorId } from '@/api/types'
import { examples } from '@/features/assistant/strings'
import type { TurnState } from '@/features/assistant/useChat'
import { LANGUAGES, type UiLanguage } from '@/i18n/translator'
import type { DictationProblem } from './dictation'
import { useDictation, useVoiceAvailability, useVoiceText } from './hooks'
import { PROBLEM_TEXT } from './problems'
import { speaker } from './speaker'
import { conversationSpeech } from './speechText'
import { LANGUAGE_NAME, type VoiceKey } from './strings'
import { VoiceOrb, type OrbMode } from './VoiceOrb'

const MAX_QUESTION_CHARS = 500 // the question box's own limit
const MAX_SILENCES = 2 // times in a row nothing is heard before the conversation ends
const PROMPT = 'voice-prompt'
const ERROR = 'voice-error'

/** Each language in its own script, whatever the page is in (as in the header's switch). */
const NATIVE_NAME: Record<UiLanguage, string> = { en: 'English', bn: 'বাংলা', hi: 'हिन्दी' }

type StopReason = 'silence' | 'error' | 'no_voice' | 'problem'

type Phase =
  | { name: 'idle' }
  | { name: 'prompting' }
  | { name: 'listening' }
  | { name: 'thinking' }
  | { name: 'speaking' }
  | { name: 'stopped'; reason: StopReason; problem: DictationProblem | null }

interface Props {
  /** The language of the interface, for the panel's own words. */
  uiLanguage: UiLanguage
  /** What the answer language box says; "automatic" means: answer in the language spoken. */
  answerChoice: LanguageChoice
  /** Ask a question; tells how it ended (null if it was cancelled). */
  onAsk: (request: AskRequest) => Promise<TurnState | null>
  /** Only answer from these sources (a scheme chosen on the page). */
  sourceIds?: string[]
  /** The sector being looked at: a nudge for the search, never a limit. */
  sector?: SectorId
  /** A typed question is waiting for its answer. */
  busy: boolean
}

const choice =
  'inline-flex min-h-12 min-w-12 items-center justify-center rounded-xl border px-4 font-medium ' +
  'disabled:cursor-not-allowed disabled:opacity-60'

/**
 * Talking with the assistant: the person speaks a question, it is asked, the answer is read
 * aloud, and then it listens again, until the person stops it, says nothing twice, or something
 * fails. The conversation appears on the page as usual, so what was said and answered can be read.
 *
 * Each step is said or shown in words: a person who cannot see the screen is told what is
 * happening, and what went wrong, by voice. The language spoken is chosen here; the answer comes
 * in the language of the answer box, or in the language spoken when that is automatic.
 *
 * Every step continues from what ended the one before (speech finished, answer arrived, listening
 * ended). Stopping, or leaving the page, starts a new `session`, so anything still on its way
 * from the old one is ignored.
 */
export function VoiceConversation({
  uiLanguage,
  answerChoice,
  onAsk,
  sourceIds,
  sector,
  busy,
}: Props) {
  const t = useVoiceText(uiLanguage)
  const [spoken, setSpoken] = useState<UiLanguage>(uiLanguage)
  const [phase, setPhase] = useState<Phase>({ name: 'idle' })
  const [said, setSaid] = useState('')
  const session = useRef(0)
  const saidRef = useRef('')
  const silences = useRef(0)
  const answers = useRef(0) // answers given in this conversation: the first carries the disclaimer
  const voice = useVoiceAvailability(spoken)

  function listen() {
    saidRef.current = ''
    setSaid('')
    setPhase({ name: 'listening' })
    dictation.start()
  }

  /** Say `text`; when it has been read to the end, listen again (or end, after a failure). */
  function say(id: string, text: string, language: UiLanguage, then: 'listen' | 'stop') {
    const mine = session.current
    const started = speaker.speak(id, text, language, (finished) => {
      if (!finished || mine !== session.current) return
      if (then === 'listen') listen()
      else setPhase({ name: 'stopped', reason: 'error', problem: null })
    })
    if (started) setPhase({ name: 'speaking' })
    else setPhase({ name: 'stopped', reason: id === ERROR ? 'error' : 'no_voice', problem: null })
  }

  function ask(question: string) {
    const mine = session.current
    setSaid(question)
    setPhase({ name: 'thinking' })
    onAsk({
      question: Array.from(question).slice(0, MAX_QUESTION_CHARS).join(''),
      language: answerChoice === 'auto' ? spoken : answerChoice,
      ...(sourceIds ? { source_ids: sourceIds } : {}),
      ...(sector ? { sector } : {}),
    }).then((state) => {
      if (!state || mine !== session.current) return // stopped, or the page was left
      if (state.status === 'done') {
        const { answer } = state
        const first = answers.current === 0
        answers.current += 1
        say(
          `voice-answer-${mine}-${Date.now()}`,
          conversationSpeech(answer, { first }),
          answer.language,
          'listen',
        )
      } else {
        say(ERROR, t('talkErrorSpoken'), spoken, 'stop')
      }
    })
  }

  const dictation = useDictation(spoken, {
    onText: (text) => {
      saidRef.current = text
      setSaid(text)
    },
    onFinish: (heard, problem) => {
      if (problem && problem !== 'no_speech') {
        setPhase({ name: 'stopped', reason: 'problem', problem })
      } else if (heard && saidRef.current.trim()) {
        silences.current = 0
        ask(saidRef.current.trim())
      } else {
        silences.current += 1
        if (silences.current >= MAX_SILENCES) {
          setPhase({ name: 'stopped', reason: 'silence', problem: null })
        } else listen()
      }
    },
  })

  // Leaving the page ends the conversation: nothing keeps talking or listening behind it.
  useEffect(
    () => () => {
      session.current += 1
      if (speaker.getSnapshot().playingId?.startsWith('voice-')) speaker.stop()
    },
    [],
  )

  /** Begin: with the prompt and listening, or with a question that was tapped. */
  function start(tapped?: string) {
    session.current += 1
    const mine = session.current
    silences.current = 0
    answers.current = 0
    saidRef.current = ''
    setSaid('')
    if (tapped) {
      ask(tapped)
      return
    }
    const started = speaker.speak(PROMPT, t('talkPrompt'), spoken, (finished) => {
      if (finished && mine === session.current) listen()
    })
    if (started) setPhase({ name: 'prompting' })
    else listen()
  }

  function stop() {
    session.current += 1
    dictation.cancel()
    speaker.stop()
    setPhase({ name: 'idle' })
  }

  const active = phase.name !== 'idle' && phase.name !== 'stopped'
  const name = t(LANGUAGE_NAME[spoken])
  const mode: OrbMode =
    phase.name === 'listening'
      ? 'listening'
      : phase.name === 'thinking'
        ? 'thinking'
        : phase.name === 'prompting' || phase.name === 'speaking'
          ? 'speaking'
          : 'idle'

  // The live region says each step; the words being recognised are shown but not announced, or
  // they would be read out again at every word.
  let status: string | null = null
  if (phase.name === 'prompting') status = t('talkPrompt')
  else if (phase.name === 'listening') status = t('talkListening')
  else if (phase.name === 'thinking') status = t('talkThinking')
  else if (phase.name === 'speaking') status = t('talkSpeaking')
  else if (phase.name === 'stopped') {
    if (phase.reason === 'silence') status = t('talkSilence')
    else if (phase.reason === 'no_voice') status = t('talkNoVoiceForAnswer')
    else if (phase.reason === 'problem' && phase.problem) {
      status = t(PROBLEM_TEXT[phase.problem], { language: name })
    } else status = t('talkErrorShown')
  }

  const chip: { key: VoiceKey; tone: string } =
    phase.name === 'stopped'
      ? { key: 'chipStopped', tone: 'bg-warn-surface text-warn' }
      : mode === 'listening'
        ? { key: 'chipListening', tone: 'bg-brand text-white' }
        : mode === 'thinking'
          ? { key: 'chipThinking', tone: 'bg-brand text-white' }
          : mode === 'speaking'
            ? { key: 'chipSpeaking', tone: 'bg-brand text-white' }
            : { key: 'chipReady', tone: 'bg-brand-soft text-brand' }

  // 0 listening, 1 looking up, 2 answering; the prompt is before the first.
  const step =
    mode === 'listening' ? 0 : mode === 'thinking' ? 1 : phase.name === 'speaking' ? 2 : -1
  const showBubble =
    said !== '' && (mode === 'listening' || mode === 'thinking' || phase.name === 'speaking')

  let unavailable: string | null = null
  if (!dictation.supported) unavailable = t('talkUnsupported')
  else if (voice === 'unsupported') unavailable = t('noSynthesis')
  else if (voice === 'missing') unavailable = t('noVoice', { language: name })

  return (
    <section
      aria-labelledby="talk-heading"
      lang={uiLanguage}
      className="space-y-5 rounded-2xl border border-line bg-surface p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 id="talk-heading" className="text-xl font-semibold">
          {t('talkTitle')}
        </h2>
        {/* A word, never a color alone; the live region below announces the same thing. */}
        <span
          aria-hidden="true"
          className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ${chip.tone}`}
        >
          <span
            className={`size-2 rounded-full bg-current ${active ? 'motion-safe:animate-pulse' : ''}`}
          />
          {t(chip.key)}
        </span>
      </div>
      <p className="max-w-prose text-muted">{t('talkIntro')}</p>

      <fieldset className="space-y-2" disabled={active}>
        <legend className="text-sm font-medium">{t('talkLanguage')}</legend>
        <div className="inline-flex flex-wrap gap-2">
          {LANGUAGES.map((code) => {
            const chosen = spoken === code
            return (
              <button
                key={code}
                type="button"
                lang={code}
                aria-pressed={chosen}
                onClick={() => setSpoken(code)}
                className={`${choice} gap-2 ${
                  chosen
                    ? 'border-brand bg-brand-soft text-brand'
                    : 'border-muted bg-surface text-ink hover:bg-brand-soft'
                }`}
              >
                {chosen && (
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    width="18"
                    height="18"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {NATIVE_NAME[code]}
              </button>
            )
          })}
        </div>
      </fieldset>

      <div className="flex flex-col items-center gap-4 py-2">
        {unavailable ? (
          <p className="max-w-prose text-center text-sm text-muted">{unavailable}</p>
        ) : (
          <button
            type="button"
            onClick={() => (active ? stop() : start())}
            disabled={!active && busy}
            className="group flex min-h-12 flex-col items-center gap-2 rounded-2xl px-6 py-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <VoiceOrb mode={mode} />
            <span className="text-lg font-semibold text-ink">
              {t(active ? 'talkStop' : 'talkStart')}
            </span>
          </button>
        )}

        {active && (
          <Steps current={step} labels={[t('stepListen'), t('stepThink'), t('stepSpeak')]} />
        )}

        {showBubble && (
          <div
            aria-hidden="true"
            className="w-full max-w-xl space-y-1 rounded-xl bg-brand-soft p-4 text-left"
          >
            <p className="text-sm font-medium text-brand">{t('talkQuestion')}</p>
            <p lang={spoken} className="text-lg text-ink">
              {said}
            </p>
          </div>
        )}

        {/* <output> is a polite live region: every step is announced to someone who cannot see. */}
        <output
          className={`block max-w-xl text-center text-lg ${
            phase.name === 'stopped' ? 'font-medium text-danger' : 'text-muted'
          }`}
        >
          {status}
        </output>
      </div>

      {!active && !unavailable && (
        <div className="space-y-2">
          <p id="talk-try" className="text-sm font-medium">
            {t('talkTryTitle')}
          </p>
          <ul aria-labelledby="talk-try" className="flex flex-col gap-2">
            {examples[spoken].map((question) => (
              <li key={question}>
                <button
                  type="button"
                  lang={spoken}
                  disabled={busy}
                  onClick={() => start(question)}
                  className="min-h-12 w-full rounded-xl border border-line bg-surface px-4 py-2 text-left hover:bg-brand-soft disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {question}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

/** Listen, look up, answer: where in the round the conversation is. Decoration for the eyes. */
function Steps({ current, labels }: { current: number; labels: string[] }) {
  return (
    <ol aria-hidden="true" className="flex items-center gap-2 text-sm">
      {labels.map((label, index): ReactNode => {
        const done = index < current
        const now = index === current
        return (
          <li key={label} className="flex items-center gap-2">
            {index > 0 && <span className="h-px w-4 bg-muted" />}
            <span
              className={`grid size-6 place-items-center rounded-full text-xs font-semibold ${
                now
                  ? 'bg-brand text-white'
                  : done
                    ? 'bg-brand-soft text-brand'
                    : 'border border-muted text-muted'
              }`}
            >
              {done ? '\u{2713}' : index + 1}
            </span>
            <span className={now ? 'font-semibold text-ink' : 'text-muted'}>{label}</span>
          </li>
        )
      })}
    </ol>
  )
}
