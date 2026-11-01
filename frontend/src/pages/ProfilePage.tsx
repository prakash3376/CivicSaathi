import { useState } from 'react'
import { secondaryButton } from '@/components/ui/buttonStyles'
import { clearChoices, readChoices, type StoredChoices } from '@/features/portal/storedChoices'
import { usePortalText } from '@/features/portal/usePortalText'
import type { PortalKey } from '@/features/portal/strings'

const LANGUAGE_NAME: Record<string, string> = {
  en: 'English',
  bn: 'বাংলা',
  hi: 'हिन्दी',
}

const SPEED: Record<string, PortalKey> = {
  slow: 'profileSlow',
  normal: 'profileNormal',
  fast: 'profileFast',
}

/**
 * My Profile. There is no account: this page says so, shows the three choices the browser keeps
 * (and nothing else), lets the person clear them, and says what is never saved.
 */
export function ProfilePage() {
  const { language, t } = usePortalText()
  const [stored, setStored] = useState<StoredChoices>(readChoices)
  const [cleared, setCleared] = useState(false)

  const rows: { label: string; value: string }[] = [
    {
      label: t('profileInterface'),
      value: (stored.interface && LANGUAGE_NAME[stored.interface]) || t('profileDefault'),
    },
    {
      label: t('profileAnswer'),
      value:
        stored.answer === 'auto'
          ? t('profileAuto')
          : (stored.answer && LANGUAGE_NAME[stored.answer]) || t('profileDefault'),
    },
    {
      label: t('profileSpeed'),
      value:
        (stored.speed && SPEED[stored.speed] && t(SPEED[stored.speed]!)) || t('profileDefault'),
    },
  ]

  return (
    <div lang={language} className="space-y-10">
      <title>{`${t('profileTitle')} \u{B7} CivicSaathi`}</title>

      <section className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('profileTitle')}</h1>
        <p className="max-w-prose text-lg text-muted">{t('profileIntro')}</p>
      </section>

      <section aria-labelledby="saved-heading" className="space-y-4">
        <h2 id="saved-heading" className="text-2xl font-bold tracking-tight">
          {t('profileSavedHeading')}
        </h2>
        <p className="max-w-prose text-muted">{t('profileSavedText')}</p>
        <dl className="max-w-xl divide-y divide-line rounded-2xl border border-line bg-surface">
          {rows.map((row) => (
            <div key={row.label} className="flex flex-wrap justify-between gap-2 p-4">
              <dt className="font-medium">{row.label}</dt>
              <dd className="text-muted">{row.value}</dd>
            </div>
          ))}
        </dl>
        <button
          type="button"
          onClick={() => {
            setStored(clearChoices())
            setCleared(true)
          }}
          className={secondaryButton}
        >
          {t('profileClear')}
        </button>
        <output className="block font-medium text-ok">{cleared ? t('profileCleared') : ''}</output>
      </section>

      <section aria-labelledby="never-heading" className="space-y-3">
        <h2 id="never-heading" className="text-2xl font-bold tracking-tight">
          {t('profileNeverHeading')}
        </h2>
        <ul className="max-w-prose list-disc space-y-2 pl-5">
          <li>{t('profileNever1')}</li>
          <li>{t('profileNever2')}</li>
          <li>{t('profileNever3')}</li>
        </ul>
      </section>

      <section
        aria-labelledby="account-heading"
        className="space-y-2 rounded-2xl border border-line bg-surface p-5"
      >
        <h2 id="account-heading" className="text-xl font-bold">
          {t('profileAccountHeading')}
        </h2>
        <p className="max-w-prose text-muted">{t('profileAccountText')}</p>
      </section>
    </div>
  )
}
