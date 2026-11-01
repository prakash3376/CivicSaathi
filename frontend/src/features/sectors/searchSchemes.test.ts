import { describe, expect, it } from 'vitest'
import type { SourceSummary } from '@/api/types'
import { documentMatches, latestUpdates } from '@/features/portal/documents'
import { healthCover } from '@/test/programmeFixtures'
import { schemesBody } from '@/test/schemeFixtures'
import { sourceBody } from '@/test/utils'
import { filterSchemes, NO_FILTERS, searchWords, statesOf } from './searchSchemes'

const [svmcm, pragati] = schemesBody.schemes as [
  (typeof schemesBody.schemes)[0],
  (typeof schemesBody.schemes)[0],
]
const all = [svmcm, pragati]

describe('searchWords', () => {
  it('lower-cases and drops punctuation', () => {
    expect(searchWords('  Which Schemes, for Farmers? ')).toEqual([
      'which',
      'schemes',
      'for',
      'farmers',
    ])
  })

  it('keeps Bengali and Hindi words whole', () => {
    expect(searchWords('বৃত্তি, छात्रवृत्ति!')).toEqual(['বৃত্তি', 'छात्रवृत्ति'])
  })

  it('is empty for nothing', () => {
    expect(searchWords(' ?! ')).toEqual([])
  })
})

describe('filterSchemes', () => {
  it('keeps everything when nothing is asked', () => {
    expect(filterSchemes(all, NO_FILTERS, 'en')).toEqual(all)
  })

  it('needs every word, in any order, in the name, department, summary or courses', () => {
    expect(filterSchemes(all, { ...NO_FILTERS, text: 'girls technical' }, 'en')).toEqual([pragati])
    expect(filterSchemes(all, { ...NO_FILTERS, text: 'diploma girls' }, 'en')).toEqual([pragati])
    expect(filterSchemes(all, { ...NO_FILTERS, text: 'girls zzz' }, 'en')).toEqual([])
  })

  it('searches the words of the language of the page', () => {
    expect(filterSchemes(all, { ...NO_FILTERS, text: 'শিক্ষার্থীদের' }, 'bn')).toEqual([svmcm])
    expect(filterSchemes(all, { ...NO_FILTERS, text: 'শিক্ষার্থীদের' }, 'en')).toEqual([])
  })

  it('filters by level and by state', () => {
    expect(filterSchemes(all, { ...NO_FILTERS, level: 'central' }, 'en')).toEqual([pragati])
    expect(filterSchemes(all, { ...NO_FILTERS, level: 'state' }, 'en')).toEqual([svmcm])
    expect(filterSchemes(all, { ...NO_FILTERS, state: 'West Bengal' }, 'en')).toEqual([svmcm])
    expect(filterSchemes(all, { text: 'girls', level: 'state', state: '' }, 'en')).toEqual([])
  })
})

describe('searching what a programme gives and who it is for', () => {
  const programmes = [healthCover, ...all]

  it('finds a programme by a word in its benefit', () => {
    // "Rs. 5,00,000 per family" is in the benefit, not in the name or the summary.
    expect(filterSchemes(programmes, { ...NO_FILTERS, text: 'family' }, 'en')).toEqual([
      healthCover,
    ])
  })

  it('finds a programme by a word in who it is for', () => {
    expect(
      filterSchemes(programmes, { ...NO_FILTERS, text: 'families of the state' }, 'en'),
    ).toEqual([healthCover])
  })

  it('does not break for a scheme that has neither', () => {
    expect(filterSchemes(all, { ...NO_FILTERS, text: 'girls' }, 'en')).toEqual([pragati])
  })
})

describe('statesOf', () => {
  it('lists each state once, sorted, and leaves out central schemes', () => {
    expect(statesOf(all)).toEqual(['West Bengal'])
    expect(statesOf([{ ...svmcm, state: 'Bihar' }, svmcm, { ...svmcm, state: 'Bihar' }])).toEqual([
      'Bihar',
      'West Bengal',
    ])
  })
})

describe('documents', () => {
  const doc = (change: Partial<SourceSummary>): SourceSummary => ({ ...sourceBody, ...change })

  it('counts only announcements as updates, newest first, undated last', () => {
    const old = doc({ id: 'a', doc_type: 'notification', document_date: '2025-01-01' })
    const recent = doc({ id: 'b', doc_type: 'circular', document_date: '2026-06-01' })
    const undated = doc({ id: 'c', doc_type: 'notification', document_date: null })
    const guide = doc({ id: 'd', doc_type: 'guidelines', document_date: '2026-09-01' })

    expect(latestUpdates([old, undated, guide, recent]).map((s) => s.id)).toEqual(['b', 'a', 'c'])
  })

  it('does not change the list it is given', () => {
    const list = [
      doc({ id: 'a', doc_type: 'notification', document_date: '2025-01-01' }),
      doc({ id: 'b', doc_type: 'notification', document_date: '2026-01-01' }),
    ]

    latestUpdates(list)

    expect(list.map((s) => s.id)).toEqual(['a', 'b'])
  })

  it('matches a document by words in its title, scheme or department', () => {
    expect(documentMatches(sourceBody, 'svmcm guidelines')).toBe(true)
    expect(documentMatches(sourceBody, 'west bengal')).toBe(true)
    expect(documentMatches(sourceBody, 'aicte')).toBe(false)
    expect(documentMatches(sourceBody, '')).toBe(true)
  })
})
