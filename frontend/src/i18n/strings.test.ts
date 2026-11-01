import { describe, expect, it } from 'vitest'
import { strings as layout } from '@/components/layout/strings'
import { strings as assistant } from '@/features/assistant/strings'
import { strings as portal } from '@/features/portal/strings'
import { strings as schemes } from '@/features/schemes/strings'
import { strings as sectors } from '@/features/sectors/strings'
import { strings as voice } from '@/features/voice/strings'
import { createTranslator, LANGUAGES, local } from './translator'

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()
const SCRIPT = {
  bn: /[\u{0980}-\u{09FF}]/u, // the Bengali block
  hi: /[\u{0900}-\u{097F}]/u, // the Devanagari block
} as const
const NATIVE_DIGIT = /[\u{09E6}-\u{09EF}\u{0966}-\u{096F}]/u // Bengali or Devanagari digits
// The name of a language is written in its own script, whatever the language around it.
const LANGUAGE_NAMES = new Set([
  'languageEnglish',
  'languageBengali',
  'languageHindi',
  'english',
  'bengali',
  'hindi',
])

const tables = { assistant, schemes, layout, voice, sectors, portal } as const

describe('the languages', () => {
  it('are English, Bengali and Hindi, in the order of the switch', () => {
    expect(LANGUAGES).toEqual(['en', 'bn', 'hi'])
  })
})

describe.each(Object.entries(tables))('the %s strings', (_name, table) => {
  const english: Record<string, string> = table.en
  const keys = Object.keys(english)

  describe.each(['bn', 'hi'] as const)('in %s', (language) => {
    const words: Record<string, string> = table[language]

    it('have the same entries as English', () => {
      expect(Object.keys(words).sort()).toEqual([...keys].sort())
    })

    it.each(keys)('use the same placeholders as English: %s', (key) => {
      expect(placeholders(words[key]!)).toEqual(placeholders(english[key]!))
    })

    it.each(keys)('are not empty: %s', (key) => {
      expect(words[key]!.trim()).not.toBe('')
    })

    it('are written in the script of the language (a few names stay as they are)', () => {
      for (const key of keys) {
        if (!LANGUAGE_NAMES.has(key)) expect(words[key], key).toMatch(SCRIPT[language])
      }
    })

    it('write figures with the digits 0-9, as the answers and schemes do', () => {
      for (const text of Object.values(words)) expect(text).not.toMatch(NATIVE_DIGIT)
    })
  })
})

describe('createTranslator', () => {
  const t = createTranslator({
    en: { hello: 'Hello {name}', plain: 'Plain' },
    bn: { hello: 'নমস্কার {name}', plain: 'সাধারণ' },
    hi: { hello: 'नमस्ते {name}', plain: 'सादा' },
  })

  it('fills in placeholders and knows its language', () => {
    expect(t('en')('hello', { name: 'Asha' })).toBe('Hello Asha')
    expect(t('bn')('hello', { name: 'Asha' })).toBe('নমস্কার Asha')
    expect(t('hi')('hello', { name: 'Asha' })).toBe('नमस्ते Asha')
    expect(t('hi').language).toBe('hi')
  })

  it('accepts numbers, and uses a placeholder more than once', () => {
    const twice = createTranslator({
      en: { k: '{n} of {n}' },
      bn: { k: '{n} এর {n}' },
      hi: { k: '{n} का {n}' },
    })

    expect(twice('en')('k', { n: 3 })).toBe('3 of 3')
  })

  it('leaves an unfilled placeholder visible rather than writing "undefined"', () => {
    expect(t('en')('hello')).toBe('Hello {name}')
  })

  it('does not treat a value as a pattern', () => {
    expect(t('en')('hello', { name: '$& {name}' })).toBe('Hello $& {name}')
  })
})

describe('local', () => {
  it('picks the wording in the chosen language', () => {
    const text = { en: 'Yes', bn: 'হ্যাঁ', hi: 'हाँ' }

    expect(local(text, 'en')).toBe('Yes')
    expect(local(text, 'bn')).toBe('হ্যাঁ')
    expect(local(text, 'hi')).toBe('हाँ')
  })
})
