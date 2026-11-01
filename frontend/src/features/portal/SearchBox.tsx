import { useId, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { primaryButton, secondaryButton } from '@/components/ui/buttonStyles'
import { MAX_QUESTION_CHARS } from '@/features/assistant/AskForm'
import { MicButton } from '@/features/voice/MicButton'
import type { PortalKey, Translate } from './strings'

const EXAMPLES: PortalKey[] = ['example1', 'example2', 'example3', 'example4', 'example5']

interface Props {
  t: Translate
  /** What the box starts with (the search page shows the words that were searched for). */
  initial?: string
  showExamples?: boolean
}

/**
 * One box for everything: type or speak a word or a question, then either search (schemes and
 * documents) or ask AI Saathi (an answer from the official documents). The microphone fills the box;
 * nothing is sent until a button is pressed.
 */
export function SearchBox({ t, initial = '', showExamples = false }: Props) {
  const ids = useId()
  const navigate = useNavigate()
  const input = useRef<HTMLInputElement>(null)
  const spoken = useRef('') // what was in the box before speaking: the words are added after it
  const [text, setText] = useState(initial)
  const trimmed = text.trim()
  const query = encodeURIComponent(trimmed)

  function search(event?: FormEvent) {
    event?.preventDefault()
    if (trimmed) void navigate(`/search?q=${query}`)
    else input.current?.focus()
  }

  function ask() {
    void navigate(trimmed ? `/ask?q=${query}` : '/ask')
  }

  function dictated(words: string) {
    setText(
      Array.from(spoken.current + words)
        .slice(0, MAX_QUESTION_CHARS)
        .join(''),
    )
  }

  return (
    <div className="space-y-4">
      <search>
        <form onSubmit={search} className="space-y-3">
          <label htmlFor={`${ids}-q`} className="sr-only">
            {t('searchLabel')}
          </label>
          <input
            id={`${ids}-q`}
            ref={input}
            type="search"
            value={text}
            maxLength={MAX_QUESTION_CHARS}
            onChange={(event) => setText(event.target.value)}
            placeholder={t('searchPlaceholder')}
            aria-describedby={`${ids}-help`}
            className="min-h-14 w-full rounded-xl border border-muted bg-surface px-4 text-lg text-ink"
          />
          <div className="flex flex-wrap gap-3">
            <button type="submit" className={primaryButton}>
              {t('searchButton')}
            </button>
            <button type="button" onClick={ask} className={secondaryButton}>
              {t('askButton')}
            </button>
          </div>
          <p id={`${ids}-help`} className="max-w-prose text-sm text-muted">
            {t('searchOrAsk')}
          </p>
        </form>
      </search>

      <MicButton
        language={t.language}
        uiLanguage={t.language}
        onStart={() => {
          spoken.current = trimmed ? `${trimmed} ` : ''
        }}
        onText={dictated}
        onFinish={() => input.current?.focus()}
      />

      {showExamples && (
        <div className="space-y-2">
          <p id={`${ids}-examples`} className="text-sm font-medium">
            {t('examplesLabel')}
          </p>
          <ul aria-labelledby={`${ids}-examples`} className="flex flex-wrap gap-2">
            {EXAMPLES.map((key) => (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => {
                    setText(t(key))
                    input.current?.focus()
                  }}
                  className="min-h-12 rounded-full border border-line bg-surface px-4 py-2 text-left hover:bg-brand-soft"
                >
                  {t(key)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
