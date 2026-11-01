import { useId, useState } from 'react'
import type { Evidence } from '@/api/types'
import { OfficialLink } from '@/features/assistant/OfficialLink'
import type { Translate } from './strings'
import { useSourceLookup } from './useSourceLookup'

interface Props {
  evidence: Evidence[]
  t: Translate
}

/** The words of the official document behind a statement, shown on request. */
export function EvidenceQuote({ evidence, t }: Props) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const sources = useSourceLookup()
  if (evidence.length === 0) return null

  return (
    <div className="space-y-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex min-h-12 items-center rounded-lg text-brand underline"
      >
        {open ? t('hideWords') : t('showWords')}
      </button>
      {open && (
        <div id={id} className="space-y-3">
          {evidence.map((item) => {
            const source = sources.get(item.source_id)
            return (
              <figure key={`${item.source_id}:${item.quote}`} className="space-y-1">
                <blockquote lang="en" className="border-l-4 border-brand pl-3">
                  {item.quote}
                </blockquote>
                <figcaption className="text-sm text-muted">
                  {source ? (
                    <>
                      {t('sourceLabel')}{' '}
                      <OfficialLink
                        url={source.url}
                        title={source.title}
                        openLabel={t('openDocument')}
                      />
                    </>
                  ) : (
                    `${t('sourceLabel')} ${item.source_id}`
                  )}
                  {item.where ? ` (${item.where})` : ''}
                </figcaption>
              </figure>
            )
          })}
        </div>
      )}
    </div>
  )
}
