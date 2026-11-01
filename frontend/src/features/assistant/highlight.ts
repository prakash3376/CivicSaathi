import type { Highlight } from '@/api/types'

export interface Segment {
  text: string
  marked: boolean
}

/**
 * Cut a passage into plain and highlighted runs, in reading order.
 *
 * The server counts positions in Unicode code points (as Python does) but JavaScript strings are
 * counted in UTF-16 units, so the two differ after any character outside the Basic Multilingual
 * Plane. The passage is therefore split into code points first. Bad ranges are clamped, empty ones
 * dropped, and overlapping ones merged: a quote is never shown twice or cut in the middle of a
 * character.
 */
export function splitByHighlights(passage: string, highlights: readonly Highlight[]): Segment[] {
  const characters = Array.from(passage)
  const clamp = (position: number) => Math.min(Math.max(position, 0), characters.length)

  const merged: Highlight[] = []
  const ranges = highlights
    .map(({ start, end }) => ({ start: clamp(start), end: clamp(end) }))
    .filter(({ start, end }) => end > start)
    .sort((a, b) => a.start - b.start)
  for (const range of ranges) {
    const last = merged.at(-1)
    if (last && range.start <= last.end) last.end = Math.max(last.end, range.end)
    else merged.push({ ...range })
  }

  const segments: Segment[] = []
  let cursor = 0
  for (const { start, end } of merged) {
    if (start > cursor)
      segments.push({ text: characters.slice(cursor, start).join(''), marked: false })
    segments.push({ text: characters.slice(start, end).join(''), marked: true })
    cursor = end
  }
  if (cursor < characters.length) {
    segments.push({ text: characters.slice(cursor).join(''), marked: false })
  }
  return segments
}
