import { useMemo } from 'react'
import { Link } from 'react-router'
import { translator } from '@/components/layout/strings'
import { primaryButton } from '@/components/ui/buttonStyles'
import { useLanguage } from '@/i18n/LanguageContext'

export function NotFoundPage() {
  const { language } = useLanguage()
  const t = useMemo(() => translator(language), [language])
  return (
    <section lang={language} className="space-y-4">
      <title>{`${t('notFoundTitle')} · CivicSaathi`}</title>
      <h1 className="text-3xl font-bold tracking-tight">{t('notFoundTitle')}</h1>
      <p className="text-muted">{t('notFoundText')}</p>
      <Link to="/" className={primaryButton}>
        {t('backHome')}
      </Link>
    </section>
  )
}
