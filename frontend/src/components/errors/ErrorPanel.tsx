import { useEffect, useMemo, useRef } from 'react'
import { ApiError } from '@/api/client'
import { translator } from '@/components/layout/strings'
import { primaryButton, secondaryButton } from '@/components/ui/buttonStyles'
import { useLanguage } from '@/i18n/LanguageContext'
import { isChunkLoadError } from './isChunkLoadError'

interface Props {
  /** What went wrong. Its message is never shown: it is for the developer, not the visitor. */
  error: unknown
  onRetry: () => void
  /** A whole page (it has the page's heading) or one part of a page (a smaller heading). */
  scope: 'page' | 'section'
}

/**
 * Tells the visitor, in their language, that something could not be shown, what still works and
 * what to do next. The reader is moved to it, because what they were waiting for is not coming.
 * Only the request id of an `ApiError` is shown (to quote when reporting): never the error's own
 * words, which may name files or internals.
 */
export function ErrorPanel({ error, onRetry, scope }: Props) {
  const { language } = useLanguage()
  const t = useMemo(() => translator(language), [language])
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    heading.current?.focus()
  }, [error])

  const page = scope === 'page'
  const requestId = error instanceof ApiError ? error.requestId : undefined
  const text = !page
    ? t('errorSectionText')
    : isChunkLoadError(error)
      ? t('errorChunkText')
      : t('errorPageText')
  const title = page ? t('errorPageTitle') : t('errorSectionTitle')
  const Heading = page ? 'h1' : 'h2'

  return (
    <div
      lang={language}
      role="alert"
      className="space-y-3 rounded-xl border border-danger bg-surface p-4"
    >
      <Heading ref={heading} tabIndex={-1} className="text-xl font-semibold text-danger">
        {title}
      </Heading>
      <p className="max-w-prose">{text}</p>
      {requestId && <p className="text-sm text-muted">{t('errorReference', { id: requestId })}</p>}
      <div className="flex flex-wrap gap-3">
        <button type="button" onClick={onRetry} className={primaryButton}>
          {t('errorTryAgain')}
        </button>
        {page && (
          // A plain link, not a router link: a full load starts from a known good state.
          <a href="/" className={secondaryButton}>
            {t('errorHome')}
          </a>
        )}
      </div>
    </div>
  )
}
