import { describe, expect, it } from 'vitest'
import { splitByHighlights } from './highlight'

describe('splitByHighlights', () => {
  it('returns the whole passage unmarked when nothing is highlighted', () => {
    expect(splitByHighlights('Income limit', [])).toEqual([{ text: 'Income limit', marked: false }])
  })

  it('marks a range and keeps the text on both sides', () => {
    expect(splitByHighlights('The income limit is 2,50,000.', [{ start: 4, end: 16 }])).toEqual([
      { text: 'The ', marked: false },
      { text: 'income limit', marked: true },
      { text: ' is 2,50,000.', marked: false },
    ])
  })

  it('handles a range at the very start or the very end', () => {
    expect(splitByHighlights('abcdef', [{ start: 0, end: 2 }])).toEqual([
      { text: 'ab', marked: true },
      { text: 'cdef', marked: false },
    ])
    expect(splitByHighlights('abcdef', [{ start: 4, end: 6 }])).toEqual([
      { text: 'abcd', marked: false },
      { text: 'ef', marked: true },
    ])
  })

  it('marks several ranges in reading order, whatever order they arrive in', () => {
    const segments = splitByHighlights('one two three', [
      { start: 8, end: 13 },
      { start: 0, end: 3 },
    ])

    expect(segments.filter((s) => s.marked).map((s) => s.text)).toEqual(['one', 'three'])
  })

  it('merges ranges that overlap or touch, so nothing is marked twice', () => {
    const segments = splitByHighlights('abcdefghij', [
      { start: 1, end: 5 },
      { start: 3, end: 7 },
      { start: 7, end: 9 },
    ])

    expect(segments).toEqual([
      { text: 'a', marked: false },
      { text: 'bcdefghi', marked: true },
      { text: 'j', marked: false },
    ])
  })

  it('clamps ranges that run past the passage and drops empty or backwards ones', () => {
    expect(splitByHighlights('abc', [{ start: 1, end: 99 }])).toEqual([
      { text: 'a', marked: false },
      { text: 'bc', marked: true },
    ])
    expect(splitByHighlights('abc', [{ start: -5, end: 1 }])[0]).toEqual({
      text: 'a',
      marked: true,
    })
    expect(
      splitByHighlights('abc', [
        { start: 2, end: 2 },
        { start: 3, end: 1 },
      ]),
    ).toEqual([{ text: 'abc', marked: false }])
  })

  it('counts positions in code points, as the server does, not in UTF-16 units', () => {
    // "𝟙" is one code point but two UTF-16 units. The server says the quote starts after
    // 3 characters ("𝟙 -"), and ends 5 later.
    const passage = '𝟙 - Rs. 2,50,000'
    const segments = splitByHighlights(passage, [{ start: 4, end: 16 }])

    expect(segments.map((s) => s.text).join('')).toBe(passage)
    expect(segments.find((s) => s.marked)?.text).toBe('Rs. 2,50,000')
  })

  it('works on Bengali text, where a character is made of several code points', () => {
    const passage = 'আয়ের সীমা ২,৫০,০০০ টাকা'
    const start = Array.from('আয়ের সীমা ').length
    const end = start + Array.from('২,৫০,০০০').length

    const marked = splitByHighlights(passage, [{ start, end }]).find((s) => s.marked)

    expect(marked?.text).toBe('২,৫০,০০০')
  })

  it('never loses or repeats a character', () => {
    const passage = 'Line one.\n\nLine two, with Rs. 2,50,000/- per annum.'
    const segments = splitByHighlights(passage, [
      { start: 3, end: 12 },
      { start: 10, end: 20 },
      { start: 30, end: 40 },
    ])

    expect(segments.map((s) => s.text).join('')).toBe(passage)
  })
})
