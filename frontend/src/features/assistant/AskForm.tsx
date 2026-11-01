import { useId, useRef, useState, type FormEvent } from 'react'
import type { LanguageChoice } from '@/api/types'
import { primaryButton } from '@/components/ui/buttonStyles'
import { MicButton } from '@/features/voice/MicButton'
import { examples, type Translate, type UiLanguage } from './strings'

/** The backend's default limit (ASSISTANT_MAX_QUESTION_CHARS); the server has the last word. */
export const MAX_QUESTION_CHARS = 500

interface Props {
  t: Translate
  /** The language of the page, which decides which example questions are offered. */
  uiLanguage: UiLanguage
  /** The language the person will speak a question in. */
  dictationLanguage: UiLanguage
  language: LanguageChoice
  onLanguageChange: (choice: LanguageChoice) => void
  onAsk: (question: string) => void
  pending: boolean
  /** Example questions help a first visit; once a conversation is going they are in the way. */
  showExamples: boolean
  /** A question to start with (from the search box), to be read and sent by the person. */
  initialQuestion?: string
}

const control =
  'min-h-12 rounded-xl border border-muted bg-surface px-3 text-ink disabled:opacity-60'

export function AskForm({
  t,
  uiLanguage,
  dictationLanguage,
  language,
  onLanguageChange,
  onAsk,
  pending,
  showExamples,
  initialQuestion = '',
}: Props) {
  const ids = useId()
  const [question, setQuestion] = useState(() =>
    Array.from(initialQuestion).slice(0, MAX_QUESTION_CHARS).join(''),
  )
  const textarea = useRef<HTMLTextAreaElement>(null)
  const trimmed = question.trim()
  const spoken = useRef('') // what was in the box before speaking: the words are added after it

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!trimmed || pending) return
    onAsk(trimmed)
    setQuestion('') // asked: the box is ready for the next question
  }

  function startDictation() {
    spoken.current = trimmed ? `${trimmed} ` : ''
  }

  function dictated(words: string) {
    setQuestion(
      Array.from(spoken.current + words)
        .slice(0, MAX_QUESTION_CHARS)
        .join(''),
    )
  }

  function fillWith(example: string) {
    setQuestion(example)
    textarea.current?.focus()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor={`${ids}-question`} className="block font-medium">
          {t('questionLabel')}
        </label>
        <textarea
          id={`${ids}-question`}
          ref={textarea}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={MAX_QUESTION_CHARS}
          rows={4}
          aria-describedby={`${ids}-hint ${ids}-count`}
          className={`${control} w-full py-3`}
        />
        <div className="flex flex-wrap justify-between gap-x-4 text-sm text-muted">
          <p id={`${ids}-hint`}>{t('questionHint')}</p>
          <p id={`${ids}-count`}>
            {t('counter', { used: Array.from(question).length, max: MAX_QUESTION_CHARS })}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <label htmlFor={`${ids}-language`} className="block font-medium">
            {t('languageLabel')}
          </label>
          <select
            id={`${ids}-language`}
            value={language}
            onChange={(event) => onLanguageChange(event.target.value as LanguageChoice)}
            className={control}
          >
            <option value="auto">{t('languageAuto')}</option>
            <option value="en">{t('languageEnglish')}</option>
            <option value="bn" lang="bn">
              {t('languageBengali')}
            </option>
            <option value="hi" lang="hi">
              {t('languageHindi')}
            </option>
          </select>
        </div>
        <button type="submit" disabled={!trimmed || pending} className={primaryButton}>
          {t('ask')}
        </button>
      </div>

      <MicButton
        language={dictationLanguage}
        uiLanguage={uiLanguage}
        onStart={startDictation}
        onText={dictated}
        onFinish={() => textarea.current?.focus()} // so the words can be checked and edited
        disabled={pending}
      />

      {showExamples && (
        <div className="space-y-2">
          <p id={`${ids}-examples`} className="text-sm text-muted">
            {t('examplesLabel')}
          </p>
          <ul aria-labelledby={`${ids}-examples`} className="flex flex-col gap-2">
            {examples[uiLanguage].map((example) => (
              <li key={example}>
                <button
                  type="button"
                  onClick={() => fillWith(example)}
                  className="min-h-12 w-full rounded-xl border border-line bg-surface px-4 py-2 text-left hover:bg-brand-soft"
                >
                  {example}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  )
}
