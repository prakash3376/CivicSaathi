import { useEffect, useRef } from 'react'
import type { EligibilityResult, Outcome, TrackView } from '@/api/types'
import { primaryButton } from '@/components/ui/buttonStyles'
import { local } from '@/i18n/translator'
import { ListenControl } from '@/features/voice/ListenControl'
import { resultSpeech } from '@/features/voice/speechText'
import { ChecklistView } from './ChecklistView'
import { EvidenceQuote } from './EvidenceQuote'
import { StatusIcon } from './StatusIcon'
import { statusOf } from './criterionStatus'
import type { StringKey, Translate } from './strings'

const banner: Record<Outcome, { heading: StringKey; text: StringKey; tone: string }> = {
  eligible: {
    heading: 'outcomeEligible',
    text: 'outcomeEligibleText',
    tone: 'border-ok text-ok',
  },
  not_eligible: {
    heading: 'outcomeNot',
    text: 'outcomeNotText',
    tone: 'border-danger text-danger',
  },
  need_more_info: {
    heading: 'outcomeMore',
    text: 'outcomeMoreText',
    tone: 'border-warn-line bg-warn-surface text-warn',
  },
}

const outcomeIcon = { eligible: 'met', not_eligible: 'not_met', need_more_info: 'unknown' } as const

interface Props {
  result: EligibilityResult
  track: TrackView
  t: Translate
  /** Take the reader to the first question that is still unanswered. */
  onAnswerMissing: () => void
}

/**
 * The outcome in words (and a mark, never color alone), the rules one by one with the official
 * words behind each, what is still needed, and the checklist.
 */
export function ResultView({ result, track, t, onAnswerMissing }: Props) {
  const heading = useRef<HTMLHeadingElement>(null)
  const language = t.language
  const { heading: headingKey, text, tone } = banner[result.outcome]

  // A new result starts at its heading, so a screen reader reads it from the top.
  useEffect(() => {
    heading.current?.focus()
  }, [result])

  // Only when answering can still change the result: a rule that is definitely not met is final.
  const missing =
    result.outcome === 'need_more_info'
      ? result.unanswered.flatMap((field) => {
          const question = track.questions.find((candidate) => candidate.field === field)
          return question ? [{ field, text: local(question.text, language) }] : []
        })
      : []

  return (
    <section aria-labelledby="result-heading" className="space-y-8">
      <div className="space-y-4">
        <h2
          id="result-heading"
          ref={heading}
          tabIndex={-1}
          className="text-2xl font-bold outline-offset-4"
        >
          {t('resultHeading')}
        </h2>

        <div className={`flex gap-3 rounded-2xl border-2 p-4 ${tone}`}>
          <StatusIcon status={outcomeIcon[result.outcome]} />
          <div className="space-y-1">
            <h3 className="text-lg font-semibold">{t(headingKey)}</h3>
            <p className="text-ink">{t(text)}</p>
          </div>
        </div>

        <ListenControl
          id="result"
          text={resultSpeech(result, track, t)}
          language={language}
          label="listenResult"
          uiLanguage={language}
        />

        {missing.length > 0 && (
          <div className="space-y-2 rounded-xl border border-line bg-surface p-4">
            <h3 className="font-semibold">{t('stillNeeded')}</h3>
            <ul className="list-disc space-y-1 pl-5">
              {missing.map((item) => (
                <li key={item.field}>{item.text}</li>
              ))}
            </ul>
            <button type="button" onClick={onAnswerMissing} className={primaryButton}>
              {t('answerThese')}
            </button>
          </div>
        )}
      </div>

      <section aria-labelledby="rules-heading" className="space-y-3">
        <h3 id="rules-heading" className="text-xl font-semibold">
          {t('rulesHeading')}
        </h3>
        <ul className="space-y-3">
          {result.criteria.map((criterion) => {
            const status = statusOf(criterion)
            return (
              <li
                key={criterion.id}
                className="space-y-1 rounded-xl border border-line bg-surface p-4"
              >
                <p className={`flex items-center gap-2 font-semibold ${status.tone}`}>
                  <StatusIcon status={status.icon} />
                  {t(status.word)}
                </p>
                <p>{local(criterion.label, language)}</p>
                {criterion.answer_text && (
                  <p className="text-sm text-muted">
                    {t('yourAnswer', { answer: local(criterion.answer_text, language) })}
                  </p>
                )}
                {criterion.note && (
                  <p className="text-sm text-muted">{local(criterion.note, language)}</p>
                )}
                <EvidenceQuote evidence={criterion.evidence} t={t} />
              </li>
            )
          })}
        </ul>
      </section>

      {result.caveats.length > 0 && (
        <section aria-labelledby="caveats-heading" className="space-y-3">
          <h3 id="caveats-heading" className="text-xl font-semibold">
            {t('caveatsHeading')}
          </h3>
          <ul className="space-y-3">
            {result.caveats.map((caveat) => (
              <li key={caveat.id} className="space-y-1">
                <p>{local(caveat.text, language)}</p>
                <EvidenceQuote evidence={caveat.evidence} t={t} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <ChecklistView checklist={result.checklist} t={t} />

      <p className="rounded-xl border border-line bg-surface p-4 text-sm text-muted">
        <strong className="text-ink">{t('disclaimerHeading')}: </strong>
        {local(result.disclaimer, language)}
      </p>
    </section>
  )
}
