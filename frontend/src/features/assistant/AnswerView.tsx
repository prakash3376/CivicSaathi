import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import type { Answer } from '@/api/types'
import { secondaryButton } from '@/components/ui/buttonStyles'
import { ListenControl } from '@/features/voice/ListenControl'
import { answerSpeech } from '@/features/voice/speechText'
import { CitationCard } from './CitationCard'
import type { Translate } from './strings'

interface Props {
  answer: Answer
  /** The words around the answer, in the language of the page. The answer's own language is
   * `answer.language`, which may differ. */
  t: Translate
  /** In a conversation each answer sits in its own turn, so its parts are not landmarks: two
   * answers would otherwise give the page several regions with the same name. */
  plain?: boolean
  /** Asks the same question again; offered when the model could not answer. */
  onRetry?: () => void
}

interface PartProps {
  plain: boolean
  labelledBy: string
  className: string
  children: ReactNode
}

/** A named region of the answer, or a plain block when the answer is one turn of a conversation. */
function Part({ plain, labelledBy, className, children }: PartProps) {
  return plain ? (
    <div className={className}>{children}</div>
  ) : (
    <section aria-labelledby={labelledBy} className={className}>
      {children}
    </section>
  )
}

/**
 * An answer: its claims, each with buttons that open the quote it rests on; what the documents do
 * not say; warnings about the sources; and the sources themselves.
 */
export function AnswerView({ answer, t, plain = false, onRetry }: Props) {
  const ids = useId()
  const [open, setOpen] = useState<ReadonlySet<number>>(new Set())
  const [focusRequest, setFocusRequest] = useState<{ number: number } | null>(null)
  const cards = useRef(new Map<number, HTMLElement>())
  const heading = useRef<HTMLHeadingElement>(null)

  // A new answer starts at its heading, so a screen reader reads it from the top.
  useEffect(() => {
    heading.current?.focus()
  }, [answer])

  // Pressing a claim's source button moves focus to that source, once it has opened.
  useEffect(() => {
    if (focusRequest) cards.current.get(focusRequest.number)?.focus()
  }, [focusRequest])

  function toggle(number: number) {
    setOpen((current) => {
      const next = new Set(current)
      if (next.has(number)) next.delete(number)
      else next.add(number)
      return next
    })
  }

  function showSource(number: number) {
    setOpen((current) => new Set(current).add(number))
    setFocusRequest({ number })
  }

  return (
    <Part plain={plain} labelledBy={`${ids}-answer`} className="space-y-5">
      <h2
        id={`${ids}-answer`}
        ref={heading}
        tabIndex={-1}
        className="text-xl font-semibold outline-offset-4"
      >
        {t('answerHeading')}
      </h2>

      <ListenControl
        id={`answer-${ids}`}
        text={answerSpeech(answer)}
        language={answer.language}
        label="listenAnswer"
        uiLanguage={t.language}
      />

      {answer.answerable ? (
        <ul className="space-y-4">
          {answer.claims.map((claim) => (
            <li key={claim.text} className="space-y-2">
              <p lang={answer.language} className="text-lg">
                {claim.text}
              </p>
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
                <span>{t('sourcesOfClaim')}</span>
                {claim.citations.map((number) => (
                  <button
                    key={number}
                    type="button"
                    aria-controls={`source-${number}`}
                    aria-expanded={open.has(number)}
                    onClick={() => showSource(number)}
                    className="inline-flex min-h-12 min-w-12 items-center justify-center rounded-xl bg-brand-soft px-4 font-medium text-brand hover:bg-line"
                  >
                    {t('source', { n: number })}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="space-y-3">
          {/* General help is not from a document: the fixed words that say so come first. */}
          {answer.guidance && answer.guidance_intro && (
            <p
              lang={answer.language}
              className="rounded-xl border border-warn-line bg-warn-surface p-4 text-warn"
            >
              {answer.guidance_intro}
            </p>
          )}
          <p
            lang={answer.language}
            className="rounded-xl border border-line bg-surface p-4 text-lg"
          >
            {answer.text}
          </p>
          {answer.guidance && answer.follow_up && (
            <p lang={answer.language} className="text-lg font-medium">
              {answer.follow_up}
            </p>
          )}
          {answer.fallback && onRetry && (
            <button type="button" onClick={onRetry} className={secondaryButton}>
              {t('tryAgain')}
            </button>
          )}
        </div>
      )}

      {answer.not_stated.length > 0 && (
        <Part plain={plain} labelledBy={`${ids}-unsaid`} className="space-y-2">
          <h3 id={`${ids}-unsaid`} className="font-semibold">
            {t('notStatedHeading')}
          </h3>
          <ul lang={answer.language} className="list-disc space-y-1 pl-5">
            {answer.not_stated.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Part>
      )}

      {answer.warnings.length > 0 && (
        <Part
          plain={plain}
          labelledBy={`${ids}-notes`}
          className="rounded-xl border border-warn-line bg-warn-surface p-4 text-warn"
        >
          <h3 id={`${ids}-notes`} className="font-semibold">
            {t('noteHeading')}
          </h3>
          <ul lang={answer.language} className="mt-2 list-disc space-y-1 pl-5">
            {answer.warnings.map((warning) => (
              <li key={`${warning.code}:${warning.source_ids.join(',')}`}>{warning.message}</li>
            ))}
          </ul>
        </Part>
      )}

      {answer.citations.length > 0 && (
        <Part plain={plain} labelledBy={`${ids}-sources`} className="space-y-3">
          <h3 id={`${ids}-sources`} className="text-lg font-semibold">
            {t('sourcesHeading')}
          </h3>
          <ol className="space-y-3">
            {answer.citations.map((citation) => (
              <CitationCard
                key={citation.number}
                citation={citation}
                t={t}
                expanded={open.has(citation.number)}
                onToggle={() => toggle(citation.number)}
                cardRef={(element) => {
                  if (element) cards.current.set(citation.number, element)
                  else cards.current.delete(citation.number)
                }}
              />
            ))}
          </ol>
        </Part>
      )}

      <p lang={answer.language} className="text-sm text-muted">
        {answer.disclaimer}
      </p>
    </Part>
  )
}
