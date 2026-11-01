import { useState, type FormEvent } from 'react'
import type { Answers, TrackView } from '@/api/types'
import { primaryButton } from '@/components/ui/buttonStyles'
import { buildAnswers, type AnswerError, type RawAnswers } from './answers'
import { fieldDomId } from './fieldIds'
import { QuestionField } from './QuestionField'
import type { Translate } from './strings'

interface Props {
  track: TrackView
  values: RawAnswers
  onChange: (field: string, value: string) => void
  onSubmit: (answers: Answers) => void
  pending: boolean
  t: Translate
}

/** The profile form: the track's questions, each optional, and a button to check. */
export function EligibilityForm({ track, values, onChange, onSubmit, pending, t }: Props) {
  const [errors, setErrors] = useState<Record<string, AnswerError>>({})

  function submit(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    const built = buildAnswers(track.questions, values)
    setErrors(built.errors)
    const first = track.questions.find((question) => built.errors[question.field])
    if (first) {
      document.getElementById(fieldDomId(first.field))?.focus()
      return
    }
    onSubmit(built.answers)
  }

  function change(field: string, value: string) {
    setErrors((current) => {
      if (!current[field]) return current
      const { [field]: _fixed, ...rest } = current
      return rest
    })
    onChange(field, value)
  }

  const failed = Object.keys(errors).length > 0
  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      {track.questions.map((question) => (
        <QuestionField
          key={question.field}
          question={question}
          value={values[question.field] ?? ''}
          onChange={(value) => change(question.field, value)}
          error={errors[question.field]}
          t={t}
        />
      ))}
      {failed && (
        <p role="alert" className="font-medium text-danger">
          {t('fixErrors')}
        </p>
      )}
      <button type="submit" disabled={pending} className={primaryButton}>
        {t('submitCheck')}
      </button>
    </form>
  )
}
