import { useEffect, useRef } from 'react'
import { ApiError } from '@/api/client'
import { primaryButton } from './buttonStyles'

interface Props {
  error: Error | null
  loadingText: string
  failureText: string
  retryLabel: string
  /** Prefix for the request id, e.g. "Reference: {id}", already filled in by the caller. */
  referenceText: (id: string) => string
  onRetry: () => void
  retrying?: boolean
}

/** What to show while something loads, or why it did not: with a way to try again. */
export function LoadNotice({
  error,
  loadingText,
  failureText,
  retryLabel,
  referenceText,
  onRetry,
  retrying = false,
}: Props) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (error) box.current?.focus()
  }, [error])

  if (!error) return <output className="block text-lg text-muted">{loadingText}</output>

  const requestId = error instanceof ApiError ? error.requestId : undefined
  return (
    <div
      ref={box}
      role="alert"
      tabIndex={-1}
      className="space-y-3 rounded-xl border border-danger bg-surface p-4"
    >
      <p className="font-semibold text-danger">{failureText}</p>
      <p>{error.message}</p>
      {requestId && <p className="text-sm text-muted">{referenceText(requestId)}</p>}
      <button type="button" onClick={onRetry} disabled={retrying} className={primaryButton}>
        {retryLabel}
      </button>
    </div>
  )
}
