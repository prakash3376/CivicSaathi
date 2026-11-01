import { describe, expect, it } from 'vitest'
import { examples, strings, translator } from './strings'

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()
const BENGALI_LETTER = /[\u{0980}-\u{09FF}]/u // the Bengali block
const DEVANAGARI_LETTER = /[\u{0900}-\u{097F}]/u // the Devanagari block
const keys = Object.keys(strings.en) as (keyof typeof strings.en)[]

describe('strings', () => {
  it('has the same entries in both languages', () => {
    expect(Object.keys(strings.bn).sort()).toEqual(Object.keys(strings.en).sort())
  })

  it.each(keys)('uses the same placeholders in both languages: %s', (key) => {
    expect(placeholders(strings.bn[key])).toEqual(placeholders(strings.en[key]))
  })

  it.each(keys)('is not empty in either language: %s', (key) => {
    expect(strings.en[key].trim()).not.toBe('')
    expect(strings.bn[key].trim()).not.toBe('')
  })

  it('writes the Bengali interface in Bengali (a few names stay as they are)', () => {
    const exceptions = new Set(['languageEnglish', 'languageHindi'])

    for (const key of keys) {
      if (!exceptions.has(key)) expect(strings.bn[key], key).toMatch(BENGALI_LETTER)
    }
  })

  it('offers example questions in both languages', () => {
    expect(examples.en.length).toBeGreaterThanOrEqual(3)
    expect(examples.bn.length).toBe(examples.en.length)
    for (const question of examples.bn) expect(question).toMatch(BENGALI_LETTER)
    expect(examples.hi.length).toBe(examples.en.length)
    for (const question of examples.hi) expect(question).toMatch(DEVANAGARI_LETTER)
  })

  it('writes figures with the digits 0-9 in the Bengali interface, as the answers do', () => {
    for (const text of Object.values(strings.bn)) expect(text).not.toMatch(/[০-৯]/u)
  })
})

describe('translator', () => {
  it('fills in placeholders', () => {
    const t = translator('en')

    expect(t('source', { n: 2 })).toBe('Source 2')
    expect(t('pages', { from: 3, to: 5 })).toBe('Pages 3 to 5')
    expect(translator('bn')('page', { n: 4 })).toBe('পৃষ্ঠা 4')
  })

  it('leaves an unfilled placeholder visible rather than writing "undefined"', () => {
    expect(translator('en')('source')).toBe('Source {n}')
  })
})
