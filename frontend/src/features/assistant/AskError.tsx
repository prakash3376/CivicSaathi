import { useEffect, useRef } from 'react'
import { ApiError } from '@/api/client'
import { primaryButton } from '@/components/ui/buttonStyles'
import type { StringKey, Translate } from './strings'

/** Failures that have wording of their own in both languages; others show the server's message. */
const KNOWN: Record<string, StringKey> = {
  network_error: 'errorNetwork',
  timeout: 'errorNetwork',
  rate_limited: 'errorBusy',
  llm_busy: 'errorBusy',
  llm_unavailable: 'errorUnavailable',
  llm_auth: 'errorUnavailable',
  llm_rejected: 'errorUnavailable',
  llm_bad_output: 'errorUnavailable',
  assistant_not_configured: 'errorUnavailable',
  index_unavailable: 'errorUnavailable',
  index_empty: 'errorUnavailable',
}

interface Props {
  error: Error
  onRetry: () => void
  t: Translate
}

/** Why no answer came, what to do, and the reference to quote if the problem persists. */
export function AskError({ error, onRetry, t }: Props) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    box.current?.focus() // move the reader here: the answer they were waiting for is not coming
  }, [error])

  const code = error instanceof ApiError ? error.code : undefined
  const known = code ? KNOWN[code] : undefined
  const requestId = error instanceof ApiError ? error.requestId : undefined

  return (
    <div
      ref={box}
      role="alert"
      tabIndex={-1}
      className="space-y-3 rounded-xl border border-danger bg-surface p-4"
    >
      <h2 className="text-lg font-semibold text-danger">{t('errorHeading')}</h2>
      <p>{known ? t(known) : error.message}</p>
      {requestId && <p className="text-sm text-muted">{t('reference', { id: requestId })}</p>}
      <button type="button" onClick={onRetry} className={primaryButton}>
        {t('tryAgain')}
      </button>
    </div>
  )
}
