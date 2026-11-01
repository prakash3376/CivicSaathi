import type { Turn } from './useChat'
import { AnswerView } from './AnswerView'
import { AskError } from './AskError'
import { RelatedSchemes } from './RelatedSchemes'
import type { Translate } from './strings'

interface Props {
  turn: Turn
  t: Translate
  onRetry: () => void
}

/** One exchange of the conversation: what was asked, then the wait, the failure or the answer. */
export function ChatTurn({ turn, t, onRetry }: Props) {
  const { state } = turn
  return (
    <li className="space-y-4">
      <div className="space-y-1">
        <p className="text-sm font-medium text-muted">{t('youAsked')}</p>
        <p className="rounded-xl bg-brand-soft p-4 text-lg text-ink">{turn.request.question}</p>
      </div>
      {/* <output> is a polite live region: the wait is announced, then the answer takes focus. */}
      {state.status === 'pending' && (
        <output className="block text-lg text-muted">{t('asking')}</output>
      )}
      {state.status === 'error' && <AskError error={state.error} onRetry={onRetry} t={t} />}
      {state.status === 'done' && (
        <>
          <AnswerView answer={state.answer} t={t} plain onRetry={onRetry} />
          <RelatedSchemes answer={state.answer} t={t} />
        </>
      )}
    </li>
  )
}
