import { useState } from 'react'
import { Link } from 'react-router'
import type { SchemeDetails } from '@/api/types'
import { primaryButton, secondaryButton } from '@/components/ui/buttonStyles'
import { ListenControl } from '@/features/voice/ListenControl'
import { schemeSpeech } from '@/features/voice/speechText'
import { local } from '@/i18n/translator'
import { DeadlineLine } from './DeadlineLine'
import { EvidenceQuote } from './EvidenceQuote'
import { levelText } from './levelText'
import { ApplyBlock, Block, ContactList, DocumentItems, NotStated, Steps } from './SchemeParts'
import type { Translate } from './strings'
import { TrackPicker } from './TrackPicker'

/** A scheme in full: what it pays, who can get it, what to gather, how to apply, what is unsaid. */
export function SchemeDetailsView({ scheme, t }: { scheme: SchemeDetails; t: Translate }) {
  const [trackId, setTrackId] = useState(scheme.tracks[0]?.id ?? null)
  const track = scheme.tracks.find((candidate) => candidate.id === trackId) ?? scheme.tracks[0]
  const language = t.language
  const checkPath = `/schemes/${scheme.id}/check${track ? `?track=${encodeURIComponent(track.id)}` : ''}`

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{scheme.name}</h1>
        <p className="text-muted">
          {scheme.authority} · {levelText(scheme, t)}
        </p>
        <p className="max-w-prose text-lg">{local(scheme.summary, language)}</p>
        <div className="flex flex-wrap gap-3 pt-1">
          <Link to={checkPath} className={primaryButton}>
            {t('checkEligibility')}
          </Link>
          <Link to={`/ask?scheme=${encodeURIComponent(scheme.id)}`} className={secondaryButton}>
            {t('askAboutScheme')}
          </Link>
        </div>
      </header>

      <ListenControl
        id={`scheme-${scheme.id}-${track?.id ?? ''}`}
        text={schemeSpeech(scheme, track, t)}
        language={language}
        label="listenScheme"
        uiLanguage={language}
      />

      <Block id="dates" heading={t('deadlinesHeading')}>
        {scheme.deadlines.length > 0 ? (
          <ul className="space-y-3">
            {scheme.deadlines.map((deadline) => (
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

      {scheme.tracks.length > 1 && (
        <TrackPicker
          legend={t('trackHeading')}
          tracks={scheme.tracks}
          value={track?.id ?? null}
          onChange={setTrackId}
          language={language}
        />
      )}

      {track && (
        <>
          <Block id="benefit" heading={t('benefitHeading')}>
            <p className="max-w-prose">{local(track.benefit.text, language)}</p>
            <EvidenceQuote evidence={track.benefit.evidence} t={t} />
          </Block>

          <Block id="criteria" heading={t('criteriaHeading')}>
            <ul className="space-y-4">
              {track.criteria.map((criterion) => (
                <li key={criterion.id} className="space-y-1">
                  <p>{local(criterion.label, language)}</p>
                  {criterion.note && (
                    <p className="text-sm text-muted">{local(criterion.note, language)}</p>
                  )}
                  <EvidenceQuote evidence={criterion.evidence} t={t} />
                </li>
              ))}
            </ul>
          </Block>

          <Block id="documents" heading={t('documentsHeading')}>
            <DocumentItems documents={track.documents} t={t} />
          </Block>

          {track.caveats.length > 0 && (
            <Block id="caveats" heading={t('caveatsHeading')}>
              <ul className="space-y-3">
                {track.caveats.map((caveat) => (
                  <li key={caveat.id} className="space-y-1">
                    <p>{local(caveat.text, language)}</p>
                    <EvidenceQuote evidence={caveat.evidence} t={t} />
                  </li>
                ))}
              </ul>
            </Block>
          )}
        </>
      )}

      <Block id="steps" heading={t('stepsHeading')}>
        <Steps steps={scheme.steps} t={t} />
      </Block>
      <Block id="apply" heading={t('applyHeading')}>
        <ApplyBlock apply={scheme.apply} t={t} />
      </Block>
      {scheme.contacts.length > 0 && (
        <Block id="contacts" heading={t('contactsHeading')}>
          <ContactList contacts={scheme.contacts} t={t} />
        </Block>
      )}
      {scheme.not_stated.length > 0 && (
        <Block id="not-stated" heading={t('notStatedHeading')}>
          <NotStated items={scheme.not_stated} t={t} />
        </Block>
      )}
    </div>
  )
}
