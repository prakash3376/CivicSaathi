import { useId, useState } from 'react'
import type { Checklist } from '@/api/types'
import { local } from '@/i18n/translator'
import { DeadlineLine } from './DeadlineLine'
import { EvidenceQuote } from './EvidenceQuote'
import { ApplyBlock, Block, ContactList, NotStated, Steps } from './SchemeParts'
import type { Translate } from './strings'

interface DocumentGroupProps {
  heading: string
  documents: Checklist['documents']
  ticked: ReadonlySet<string>
  onToggle: (id: string) => void
  t: Translate
}

function DocumentGroup({ heading, documents, ticked, onToggle, t }: DocumentGroupProps) {
  const id = useId()
  if (documents.length === 0) return null
  return (
    <div className="space-y-2">
      <h3 id={id} className="font-semibold">
        {heading}
      </h3>
      <ul aria-labelledby={id} className="space-y-2">
        {documents.map((document) => (
          <li key={document.id} className="space-y-1 rounded-xl border border-line bg-surface p-3">
            <label className="flex min-h-12 cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={ticked.has(document.id)}
                onChange={() => onToggle(document.id)}
                className="mt-1 size-5 shrink-0 accent-brand"
              />
              <span>
                <span className="block font-medium">{local(document.label, t.language)}</span>
                {document.detail && (
                  <span className="block text-sm text-muted">
                    {local(document.detail, t.language)}
                  </span>
                )}
              </span>
            </label>
            <EvidenceQuote evidence={document.evidence} t={t} />
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * What to do next: documents to gather (to tick off), the steps, the dates, where to apply and
 * whom to ask. The ticks live only on this page; nothing is saved.
 */
export function ChecklistView({ checklist, t }: { checklist: Checklist; t: Translate }) {
  const [ticked, setTicked] = useState<ReadonlySet<string>>(new Set())
  const needed = checklist.documents.filter((document) => document.applicability === 'needed')
  const maybe = checklist.documents.filter((document) => document.applicability === 'maybe')

  function toggle(id: string) {
    setTicked((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="space-y-8">
      <Block id="checklist" heading={t('checklistHeading')}>
        <p className="text-muted">{t('checklistIntro')}</p>
        <DocumentGroup
          heading={t('checklistNeededNow')}
          documents={needed}
          ticked={ticked}
          onToggle={toggle}
          t={t}
        />
        <DocumentGroup
          heading={t('checklistMaybe')}
          documents={maybe}
          ticked={ticked}
          onToggle={toggle}
          t={t}
        />
        <p aria-live="polite" className="text-sm text-muted">
          {t('checklistDone', {
            done: checklist.documents.filter((document) => ticked.has(document.id)).length,
            total: checklist.documents.length,
          })}
        </p>
      </Block>

      <Block id="checklist-dates" heading={t('deadlinesHeading')}>
        {checklist.deadlines.length > 0 ? (
          <ul className="space-y-3">
            {checklist.deadlines.map((deadline) => (
              <li key={deadline.id} className="space-y-1">
                <DeadlineLine deadline={deadline} t={t} />
                <EvidenceQuote evidence={deadline.evidence} t={t} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted">{t('deadlineNone')}</p>
        )}
      </Block>

      <Block id="checklist-steps" heading={t('stepsHeading')}>
        <Steps steps={checklist.steps} t={t} />
      </Block>
      <Block id="checklist-apply" heading={t('applyHeading')}>
        <ApplyBlock apply={checklist.apply} t={t} />
      </Block>
      {checklist.contacts.length > 0 && (
        <Block id="checklist-contacts" heading={t('contactsHeading')}>
          <ContactList contacts={checklist.contacts} t={t} />
        </Block>
      )}
      {checklist.not_stated.length > 0 && (
        <Block id="checklist-not-stated" heading={t('notStatedHeading')}>
          <NotStated items={checklist.not_stated} t={t} />
        </Block>
      )}
    </div>
  )
}
