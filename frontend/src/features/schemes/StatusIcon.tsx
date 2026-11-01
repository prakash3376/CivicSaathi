import type { CriterionStatus } from '@/api/types'

const paths: Record<CriterionStatus | 'waived', string> = {
  met: 'M5 13l4 4L19 7',
  not_met: 'M6 6l12 12M18 6L6 18',
  unknown: 'M9.5 9a2.5 2.5 0 114 2c-.8.6-1.5 1.1-1.5 2.2M12 17h.01',
  waived: 'M5 12h14',
}

/** A mark for a result. Always paired with words: it never carries the meaning alone. */
export function StatusIcon({ status }: { status: CriterionStatus | 'waived' }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      width="24"
      height="24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0"
    >
      <path d={paths[status]} />
    </svg>
  )
}
