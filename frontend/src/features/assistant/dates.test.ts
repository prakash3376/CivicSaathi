import { describe, expect, it } from 'vitest'
import { formatDate } from './dates'

describe('formatDate', () => {
  it('writes a date as day, short month and year, with the digits 0-9', () => {
    expect(formatDate('2026-04-28')).toBe('28 Apr 2026')
  })

  it('reads a time with a zone and shows its date in UTC, whatever the reader time zone', () => {
    expect(formatDate('2026-10-31T23:30:00+00:00')).toBe('31 Oct 2026')
    expect(formatDate('2026-10-31T09:00:00+05:30')).toBe('31 Oct 2026')
  })

  it('spells the month in Bengali for a Bengali page, still with the digits 0-9', () => {
    expect(formatDate('2026-04-28', 'bn')).toBe('28 এপ্রিল, 2026')
    expect(formatDate('2021-11-10', 'bn')).toBe('10 নভেম্বর, 2021')
    expect(formatDate('2026-10-31T09:00:00+00:00', 'bn')).toBe('31 অক্টোবর, 2026')
  })

  it('writes English dates when no language is given', () => {
    expect(formatDate('2026-04-28')).toBe(formatDate('2026-04-28', 'en'))
  })

  it('shows nothing for a missing or unreadable date', () => {
    for (const language of ['en', 'bn'] as const) {
      expect(formatDate(null, language)).toBe('')
      expect(formatDate('', language)).toBe('')
      expect(formatDate('next week', language)).toBe('')
    }
  })
})
