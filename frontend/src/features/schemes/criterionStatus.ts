import type { CriterionResult } from '@/api/types'
import type { StringKey } from './strings'

/** How a rule's result is shown: a mark, the words for it, and its color. */
export function statusOf(criterion: CriterionResult): {
  icon: 'met' | 'not_met' | 'unknown' | 'waived'
  word: StringKey
  tone: string
} {
  if (criterion.waived) return { icon: 'waived', word: 'statusWaived', tone: 'text-ok' }
  if (criterion.status === 'met') return { icon: 'met', word: 'statusMet', tone: 'text-ok' }
  if (criterion.status === 'not_met') {
    return { icon: 'not_met', word: 'statusNotMet', tone: 'text-danger' }
  }
  return { icon: 'unknown', word: 'statusUnknown', tone: 'text-warn' }
}
