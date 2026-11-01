import { useId } from 'react'
import type { Question } from '@/api/types'
import { local } from '@/i18n/translator'
import type { AnswerError } from './answers'
import { fieldDomId } from './fieldIds'
import type { Translate } from './strings'

interface Props {
  question: Question
  value: string
  onChange: (value: string) => void
  error?: AnswerError
  t: Translate
}

const box = 'space-y-2 rounded-xl border border-line bg-surface p-4'
const option =
  'flex min-h-12 cursor-pointer items-center gap-2 rounded-xl border border-muted bg-surface px-4 ' +
  'has-[:checked]:border-brand has-[:checked]:bg-brand-soft'

/** One question of the check. Every question can be skipped, and skipping is the starting point. */
export function QuestionField({ question, value, onChange, error, t }: Props) {
  const ids = useId()
  const language = t.language
  const text = local(question.text, language)
  const hint = question.hint ? local(question.hint, language) : null

  if (question.type === 'number') {
    const errorText = error ? t(error.key, { ...error.fields }) : null
    const describedBy = [hint && `${ids}-hint`, errorText && `${ids}-error`]
      .filter(Boolean)
      .join(' ')
    return (
      <div className={box}>
        <label htmlFor={fieldDomId(question.field)} className="block font-medium">
          {text}
        </label>
        {hint && (
          <p id={`${ids}-hint`} className="text-sm text-muted">
            {hint}
          </p>
        )}
        <div className="flex items-center gap-3">
          <input
            id={fieldDomId(question.field)}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            aria-invalid={errorText ? true : undefined}
            aria-describedby={describedBy || undefined}
            className="min-h-12 w-full max-w-xs rounded-xl border border-muted bg-surface px-3 text-ink"
          />
          {question.unit && <span className="text-muted">{local(question.unit, language)}</span>}
        </div>
        {errorText && (
          <p id={`${ids}-error`} className="font-medium text-danger">
            {errorText}
          </p>
        )}
      </div>
    )
  }

  const choices =
    question.type === 'yes_no'
      ? [
          { id: 'yes', label: t('yes') },
          { id: 'no', label: t('no') },
        ]
      : question.choices.map((choice) => ({ id: choice.id, label: local(choice.label, language) }))

  return (
    // The group takes focus when the page asks for this answer; tabIndex lets it.
    <fieldset id={fieldDomId(question.field)} tabIndex={-1} className={box}>
      <legend className="px-1 font-medium">{text}</legend>
      {hint && <p className="text-sm text-muted">{hint}</p>}
      <div className="flex flex-wrap gap-2">
        {[...choices, { id: '', label: t('skip') }].map((choice) => (
          <label key={choice.id || 'skip'} className={option}>
            <input
              type="radio"
              name={ids}
              value={choice.id}
              checked={value === choice.id}
              onChange={() => onChange(choice.id)}
              className="size-5 accent-brand"
            />
            {choice.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
