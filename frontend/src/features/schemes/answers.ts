import type { Answers, Question } from '@/api/types'

/** What each control holds: text, where an empty string means the question was skipped. */
export type RawAnswers = Readonly<Record<string, string>>

export type AnswerErrorKey = 'invalidNumber' | 'numberTooSmall' | 'numberTooLarge' | 'numberWhole'

export interface AnswerError {
  key: AnswerErrorKey
  fields?: { min?: number; max?: number }
}

const NATIVE_DIGITS = /[\u{0966}-\u{096F}\u{09E6}-\u{09EF}]/gu // Devanagari, then Bengali
const BENGALI_ZERO = 0x09e6
const DEVANAGARI_ZERO = 0x0966

/** Someone typing in Hindi or Bengali may use their own digits: read them as 0-9 (and drop , and spaces). */
export function normalizeNumber(text: string): string {
  return text
    .replace(NATIVE_DIGITS, (digit) => {
      const code = digit.codePointAt(0) ?? DEVANAGARI_ZERO
      return String(code - (code >= BENGALI_ZERO ? BENGALI_ZERO : DEVANAGARI_ZERO))
    })
    .replace(/[,\s]/g, '')
}

/** A number the person typed, `null` if the box is empty, or why it cannot be used. */
export function parseNumber(
  text: string,
  question: Pick<Question, 'integer' | 'minimum' | 'maximum'>,
): { value: number | null } | { error: AnswerError } {
  const cleaned = normalizeNumber(text)
  if (cleaned === '') return { value: null }
  if (!/^\d+(\.\d+)?$/.test(cleaned)) return { error: { key: 'invalidNumber' } }
  const value = Number(cleaned)
  if (!Number.isFinite(value)) return { error: { key: 'invalidNumber' } }
  if (question.integer && !Number.isInteger(value)) return { error: { key: 'numberWhole' } }
  if (question.minimum !== null && value < question.minimum) {
    return { error: { key: 'numberTooSmall', fields: { min: question.minimum } } }
  }
  if (question.maximum !== null && value > question.maximum) {
    return { error: { key: 'numberTooLarge', fields: { max: question.maximum } } }
  }
  return { value }
}

/**
 * The answers to send, from what the controls hold. A skipped question is left out, never sent as
 * a guess. A number that cannot be used is reported against its question and nothing is sent.
 */
export function buildAnswers(
  questions: readonly Question[],
  raw: RawAnswers,
): { answers: Answers; errors: Record<string, AnswerError> } {
  const answers: Answers = {}
  const errors: Record<string, AnswerError> = {}
  for (const question of questions) {
    const text = raw[question.field] ?? ''
    if (question.type === 'yes_no') {
      if (text === 'yes') answers[question.field] = true
      else if (text === 'no') answers[question.field] = false
    } else if (question.type === 'choice') {
      if (question.choices.some((choice) => choice.id === text)) answers[question.field] = text
    } else {
      const parsed = parseNumber(text, question)
      if ('error' in parsed) errors[question.field] = parsed.error
      else if (parsed.value !== null) answers[question.field] = parsed.value
    }
  }
  return { answers, errors }
}
