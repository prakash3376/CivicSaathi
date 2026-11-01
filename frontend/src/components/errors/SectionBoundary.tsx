import type { ReactNode } from 'react'
import { ErrorBoundary } from './ErrorBoundary'
import { ErrorPanel } from './ErrorPanel'

/** An {@link ErrorBoundary} for one part of a page, with the standard "try this part again". */
export function SectionBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      fallback={(error, reset) => <ErrorPanel scope="section" error={error} onRetry={reset} />}
    >
      {children}
    </ErrorBoundary>
  )
}
