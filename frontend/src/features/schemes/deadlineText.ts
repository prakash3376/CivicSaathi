import type { DeadlineView } from '@/api/types'
import { formatDate } from '@/features/assistant/dates'
import { local } from '@/i18n/translator'
import type { Translate } from './strings'

/** A date from the documents and what it means today, in words. */
export function deadlineText(deadline: DeadlineView, t: Translate): string {
  const fields = {
    label: local(deadline.label, t.language),
    date: formatDate(deadline.on, t.language),
  }
  if (deadline.status === 'closed') return t('deadlineClosed', fields)
  if (deadline.status === 'closes_today') return t('deadlineToday', fields)
  if (deadline.days_left === 1) return t('deadlineOpenOneDay', fields)
  return t('deadlineOpen', { ...fields, days: t('daysLeft', { n: deadline.days_left ?? 0 }) })
}
