import type { SectorId } from '@/api/types'
import { SECTOR_ICON } from './sectors'

/** The picture of a sector. Decoration only: the name beside it always says what it is. */
export function SectorIcon({ id, size = 28 }: { id: SectorId; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {SECTOR_ICON[id].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  )
}
