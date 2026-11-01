import type { DeadlineView } from '@/api/types'
import { deadlineText } from './deadlineText'
import type { Translate } from './strings'

/** A date from the documents and what it means today, in words (never by color alone). */
export function DeadlineLine({ deadline, t }: { deadline: DeadlineView; t: Translate }) {
  const urgent = deadline.status !== 'open'
  return (
    <div className="space-y-1">
      <p className={urgent ? 'font-semibold text-danger' : 'font-medium'}>
        {deadlineText(deadline, t)}
      </p>
      {deadline.scanned && <p className="text-sm text-warn">{t('deadlineScanned')}</p>}
    </div>
  )
}
