import type { ReactNode } from 'react'
import type { Apply, ChecklistDocument, Contact, LocalText, Step } from '@/api/types'
import { secondaryButton } from '@/components/ui/buttonStyles'
import { isWebAddress } from '@/features/assistant/links'
import { local } from '@/i18n/translator'
import { EvidenceQuote } from './EvidenceQuote'
import type { Translate } from './strings'

/** A titled block of a scheme screen. */
export function Block({
  id,
  heading,
  children,
}: {
  id: string
  heading: string
  children: ReactNode
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="text-xl font-semibold">
        {heading}
      </h2>
      {children}
    </section>
  )
}

export function Steps({ steps, t }: { steps: Step[]; t: Translate }) {
  return (
    <ol className="list-decimal space-y-3 pl-6">
      {steps.map((step) => (
        <li key={step.id} className="space-y-1">
          <p>{local(step.text, t.language)}</p>
          <EvidenceQuote evidence={step.evidence} t={t} />
        </li>
      ))}
    </ol>
  )
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE = /^\+?[\d\s\-()]{6,}$/

/** E-mail addresses and phone numbers become links that open the mail or phone app. */
export function ContactList({ contacts, t }: { contacts: Contact[]; t: Translate }) {
  return (
    <ul className="space-y-3">
      {contacts.map((contact) => {
        let href: string | null = null
        let label = contact.value
        if (EMAIL.test(contact.value)) {
          href = `mailto:${contact.value}`
          label = t('emailLabel', { value: contact.value })
        } else if (PHONE.test(contact.value)) {
          href = `tel:${contact.value.replace(/[^\d+]/g, '')}`
          label = t('phoneLabel', { value: contact.value })
        }
        return (
          <li key={contact.id} className="space-y-1">
            <p className="text-sm text-muted">{local(contact.label, t.language)}</p>
            {href ? (
              <a
                href={href}
                className="inline-flex min-h-12 items-center rounded-lg text-brand underline"
              >
                {label}
              </a>
            ) : (
              <p>{label}</p>
            )}
            <EvidenceQuote evidence={contact.evidence} t={t} />
          </li>
        )
      })}
    </ul>
  )
}

/** Where to apply. An address that is not a web page is shown as text, never as a link. */
export function ApplyBlock({ apply, t }: { apply: Apply; t: Translate }) {
  return (
    <div className="space-y-3">
      <p>{local(apply.text, t.language)}</p>
      {isWebAddress(apply.url) ? (
        <a href={apply.url} target="_blank" rel="noopener noreferrer" className={secondaryButton}>
          {apply.url.replace(/^https?:\/\//, '')}
          <span className="sr-only"> ({t('openApply')})</span>
        </a>
      ) : (
        <p>{apply.url}</p>
      )}
      <EvidenceQuote evidence={apply.evidence} t={t} />
    </div>
  )
}

/** What a person might expect to find that the official documents do not say. */
export function NotStated({ items, t }: { items: LocalText[]; t: Translate }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((item) => (
        <li key={item.en}>{local(item, t.language)}</li>
      ))}
    </ul>
  )
}

export function DocumentItems({ documents, t }: { documents: ChecklistDocument[]; t: Translate }) {
  return (
    <ul className="space-y-3">
      {documents.map((document) => (
        <li key={document.id} className="space-y-1">
          <p className="font-medium">
            {local(document.label, t.language)}
            {document.applicability === 'maybe' && (
              <span className="ml-2 rounded-md bg-warn-surface px-2 py-0.5 text-sm font-normal text-warn">
                {t('documentsMaybe')}
              </span>
            )}
          </p>
          {document.detail && (
            <p className="text-sm text-muted">{local(document.detail, t.language)}</p>
          )}
          <EvidenceQuote evidence={document.evidence} t={t} />
        </li>
      ))}
    </ul>
  )
}
