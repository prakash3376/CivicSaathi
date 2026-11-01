import { describe, expect, it } from 'vitest'
import type { Question } from '@/api/types'
import { schemeDetailsBody } from '@/test/schemeFixtures'
import { buildAnswers, normalizeNumber, parseNumber } from './answers'

const ug = schemeDetailsBody.tracks[0]!.questions
const income = ug.find((q) => q.field === 'family_income')!
const marks = ug.find((q) => q.field === 'marks_percent')!

describe('normalizeNumber', () => {
  it('drops commas and spaces, as people write 2,50,000', () => {
    expect(normalizeNumber('2,50,000')).toBe('250000')
    expect(normalizeNumber(' 2 50 000 ')).toBe('250000')
  })

  it('reads Devanagari digits as 0-9', () => {
    expect(normalizeNumber('\u{0968},\u{096B}\u{0966},\u{0966}\u{0966}\u{0966}')).toBe('250000')
    expect(normalizeNumber('\u{096F}\u{096E}.\u{096B}')).toBe('98.5')
  })

  it('reads digits of both kinds in one number', () => {
    expect(normalizeNumber('\u{0968}\u{09EB}0')).toBe('250')
  })

  it('reads Bengali digits as 0-9', () => {
    expect(normalizeNumber('\u{09E8}\u{09EB}\u{09E6}\u{09E6}\u{09E6}\u{09E6}')).toBe('250000')
    expect(normalizeNumber('\u{09EF}\u{09EE}.\u{09EB}')).toBe('98.5')
  })
})

describe('parseNumber', () => {
  it('an empty box is a skipped question, not zero', () => {
    expect(parseNumber('', income)).toEqual({ value: null })
    expect(parseNumber('   ', income)).toEqual({ value: null })
  })

  it('accepts a whole number and a decimal where decimals are allowed', () => {
    expect(parseNumber('250000', income)).toEqual({ value: 250000 })
    expect(parseNumber('59.99', marks)).toEqual({ value: 59.99 })
  })

  it.each(['abc', '12abc', '-5', '1e5', '1.2.3', '.5', '5.', 'Rs 500'])(
    'refuses what is not a plain number: %s',
    (text) => {
      expect(parseNumber(text, marks)).toEqual({ error: { key: 'invalidNumber' } })
    },
  )

  it('refuses a fraction where a whole number is wanted', () => {
    expect(parseNumber('1000.5', income)).toEqual({ error: { key: 'numberWhole' } })
  })

  it('refuses a number outside the question range, and says the limit', () => {
    expect(parseNumber('100.5', marks)).toEqual({
      error: { key: 'numberTooLarge', fields: { max: 100 } },
    })
    const positive: Pick<Question, 'integer' | 'minimum' | 'maximum'> = {
      integer: false,
      minimum: 1,
      maximum: null,
    }
    expect(parseNumber('0', positive)).toEqual({
      error: { key: 'numberTooSmall', fields: { min: 1 } },
    })
  })

  it('accepts the limits themselves', () => {
    expect(parseNumber('0', marks)).toEqual({ value: 0 })
    expect(parseNumber('100', marks)).toEqual({ value: 100 })
  })

  it('refuses a number too large to be exact', () => {
    expect(parseNumber('9'.repeat(400), { integer: false, minimum: null, maximum: null })).toEqual({
      error: { key: 'invalidNumber' },
    })
  })
})

describe('buildAnswers', () => {
  it('sends only what was answered, as the right kind of value', () => {
    const { answers, errors } = buildAnswers(ug, {
      institution_in_west_bengal: 'yes',
      family_income: '2,50,000',
      board_topper: 'no',
      marks_percent: '72.5',
    })

    expect(errors).toEqual({})
    expect(answers).toEqual({
      institution_in_west_bengal: true,
      family_income: 250000,
      board_topper: false,
      marks_percent: 72.5,
    })
  })

  it('leaves a skipped question out rather than guessing', () => {
    const { answers } = buildAnswers(ug, { institution_in_west_bengal: '', family_income: '' })

    expect(answers).toEqual({})
    expect('institution_in_west_bengal' in answers).toBe(false)
  })

  it('reports a bad number against its question and still reads the others', () => {
    const { answers, errors } = buildAnswers(ug, {
      institution_in_west_bengal: 'yes',
      family_income: 'lots',
    })

    expect(errors).toEqual({ family_income: { key: 'invalidNumber' } })
    expect(answers).toEqual({ institution_in_west_bengal: true })
  })

  it('ignores a choice that is not offered', () => {
    const choice = schemeDetailsBody.tracks[0]!.questions[0]!
    const withChoices: Question = {
      ...choice,
      field: 'admission_type',
      type: 'choice',
      choices: [{ id: 'first_year', label: { en: 'First', bn: 'প্রথম', hi: 'पहला' } }],
    }

    expect(buildAnswers([withChoices], { admission_type: 'first_year' }).answers).toEqual({
      admission_type: 'first_year',
    })
    expect(buildAnswers([withChoices], { admission_type: 'hacked' }).answers).toEqual({})
  })

  it('ignores answers to questions that are not asked', () => {
    expect(buildAnswers(ug, { gender: 'female' }).answers).toEqual({})
  })
})
