import type { ReactNode } from 'react'
import { ApiError } from '@/api/client'
import { primaryButton } from '@/components/ui/buttonStyles'
import { useHealth } from './useHealth'

function formatUptime(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
  if (minutes < 1) return `${Math.floor(totalSeconds)} s`
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

const dotColor = { pending: 'bg-muted', ok: 'bg-ok', danger: 'bg-danger' }

/** The status is always spelled out in words; the colored dot is only decoration. */
function StatusLine({ tone, children }: { tone: keyof typeof dotColor; children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 font-medium">
      <span aria-hidden="true" className={`inline-block size-3 rounded-full ${dotColor[tone]}`} />
      {children}
    </p>
  )
}

/** Shows whether the browser can reach the backend, and what the backend reports about itself. */
export function HealthStatus() {
  const query = useHealth()

  let body: ReactNode
  if (query.isPending) {
    body = <StatusLine tone="pending">Checking the server…</StatusLine>
  } else if (query.isError) {
    const requestId = query.error instanceof ApiError ? query.error.requestId : undefined
    body = (
      <>
        <div className="text-danger">
          <StatusLine tone="danger">Server unavailable</StatusLine>
        </div>
        <p className="text-muted">{query.error.message}</p>
        {requestId && (
          <p className="text-sm text-muted">
            Reference: <code>{requestId}</code>
          </p>
        )}
      </>
    )
  } else {
    const { service, version, environment, uptime_seconds } = query.data
    body = (
      <>
        <div className="text-ok">
          <StatusLine tone="ok">Connected</StatusLine>
        </div>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted">Service</dt>
          <dd>{service}</dd>
          <dt className="text-muted">Version</dt>
          <dd>{version}</dd>
          <dt className="text-muted">Environment</dt>
          <dd>{environment}</dd>
          <dt className="text-muted">Uptime</dt>
          <dd>{formatUptime(uptime_seconds)}</dd>
        </dl>
      </>
    )
  }

  return (
    <section
      aria-labelledby="status-heading"
      className="rounded-2xl border border-line bg-surface p-5 shadow-sm"
    >
      <h2 id="status-heading" className="text-lg font-semibold">
        System status
      </h2>
      {/* <output> is a polite live region, so screen readers announce the result when it arrives. */}
      <output className="mt-3 block space-y-3">{body}</output>
      {query.isError && (
        <button
          type="button"
          onClick={() => void query.refetch()}
          disabled={query.isFetching}
          className={`${primaryButton} mt-4`}
        >
          {query.isFetching ? 'Checking…' : 'Try again'}
        </button>
      )}
    </section>
  )
}
