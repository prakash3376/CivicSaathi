import { Link } from 'react-router'
import type { ProgrammeDetails, Statement } from '@/api/types'
import { primaryButton, secondaryButton } from '@/components/ui/buttonStyles'
import { isWebAddress } from '@/features/assistant/links'
import { formatDate } from '@/features/assistant/dates'
import { OfficialLink } from '@/features/assistant/OfficialLink'
import { local } from '@/i18n/translator'
import { EvidenceQuote } from './EvidenceQuote'
import { levelText } from './levelText'
import { KindBadges } from './SchemeCard'
import { Block } from './SchemeParts'
import type { Translate } from './strings'

/** Facts in English, each with the official words behind it on request. */
function Statements({
  items,
  t,
  ordered = false,
}: {
  items: Statement[]
  t: Translate
  ordered?: boolean
}) {
  const List = ordered ? 'ol' : 'ul'
  return (
    <List className={`space-y-3 pl-6 ${ordered ? 'list-decimal' : 'list-disc'}`}>
      {items.map((item) => (
        <li key={item.text} className="space-y-1">
          <p lang="en" className="max-w-prose">
            {item.text}
          </p>
          <EvidenceQuote evidence={item.evidence} t={t} />
        </li>
      ))}
    </List>
  )
}

/**
 * A programme or service in full: what it gives, who it is for, who is left out, what to bring, how
 * to apply, the official portal and the sources. Everything is a statement taken from an official
 * document, and a person can open the document's own words. What the documents do not say is listed.
 */
export function ProgrammeDetailsView({ scheme, t }: { scheme: ProgrammeDetails; t: Translate }) {
  const language = t.language
  const checked = formatDate(scheme.last_verified, language)
  const dated = formatDate(scheme.published_on, language)
  const showEnglishNote = language !== 'en'

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <KindBadges kind={scheme.kind} status={scheme.status} t={t} />
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{scheme.name}</h1>
        <p className="text-muted">
          {scheme.authority} · {levelText(scheme, t)}
        </p>
        <p className="max-w-prose text-lg">{local(scheme.summary, language)}</p>
        <p className="max-w-prose">
          <span className="text-muted">{t('whoFor')}: </span>
          {local(scheme.target, language)}
        </p>
        {scheme.kind === 'infrastructure' && (
          <p className="max-w-prose rounded-xl bg-brand-soft p-3 text-brand">
            {t('kindInfrastructureNote')}
          </p>
        )}
        {scheme.status !== 'active' && scheme.status_note && (
          <p lang="en" className="max-w-prose rounded-xl bg-warn-surface p-3 text-warn">
            {scheme.status_note}
          </p>
        )}
        {scheme.applicable_states.length > 0 && (
          <p className="text-muted">
            {t('stateOnly', { states: scheme.applicable_states.join(', ') })}
          </p>
        )}
        <p className="text-sm text-muted">
          {[
            checked && t('verifiedOn', { date: checked }),
            dated && t('publishedOn', { date: dated }),
          ]
            .filter(Boolean)
            .join(' · ')}
        </p>
        <div className="flex flex-wrap gap-3 pt-1">
          {isWebAddress(scheme.apply.url) && (
            <a
              href={scheme.apply.url}
              target="_blank"
              rel="noopener noreferrer"
              className={primaryButton}
            >
              {t('openPortal')}
              <span className="sr-only">
                : {scheme.apply.label} ({t('openApply')})
              </span>
            </a>
          )}
          <Link to={`/ask?scheme=${encodeURIComponent(scheme.id)}`} className={secondaryButton}>
            {t('askAboutScheme')}
          </Link>
        </div>
        {showEnglishNote && <p className="max-w-prose text-sm text-muted">{t('englishNote')}</p>}
      </header>

      <Block id="benefit" heading={t('benefitHeading')}>
        <Statements items={scheme.benefits} t={t} />
      </Block>

      {scheme.eligibility.length > 0 && (
        <Block id="eligibility" heading={t('eligibilityHeading')}>
          <Statements items={scheme.eligibility} t={t} />
        </Block>
      )}

      {scheme.exclusions.length > 0 && (
        <Block id="exclusions" heading={t('exclusionsHeading')}>
          <Statements items={scheme.exclusions} t={t} />
        </Block>
      )}

      {scheme.documents.length > 0 && (
        <Block id="bring" heading={t('bringHeading')}>
          <Statements items={scheme.documents} t={t} />
        </Block>
      )}

      {scheme.steps.length > 0 && (
        <Block id="how" heading={t('howHeading')}>
          <Statements items={scheme.steps} t={t} ordered />
        </Block>
      )}

      <Block id="portal" heading={t('portalHeading')}>
        <p lang="en">{scheme.apply.label}</p>
        <EvidenceQuote evidence={scheme.apply.evidence} t={t} />
      </Block>

      {scheme.not_stated.length > 0 && (
        <Block id="not-stated" heading={t('notStatedHeading')}>
          <ul className="list-disc space-y-1 pl-5">
            {scheme.not_stated.map((item) => (
              <li key={item} lang="en">
                {item}
              </li>
            ))}
          </ul>
        </Block>
      )}

      <Block id="sources" heading={t('sourcesHeading')}>
        <ul className="space-y-1">
          {scheme.sources.map((source) => (
            <li key={source.id}>
              <OfficialLink
                url={source.url}
                title={source.title}
                openLabel={t('openDocument')}
                className="inline-flex min-h-12 items-center"
              />
            </li>
          ))}
        </ul>
      </Block>
    </div>
  )
}
