import { useMemo, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { useLanguage } from '@/i18n/LanguageContext'
import { LanguageSwitch } from './LanguageSwitch'
import { translator, type LayoutKey } from './strings'

const navLink =
  'inline-flex min-h-12 items-center rounded-lg px-3 font-medium text-brand underline-offset-4 ' +
  'hover:underline aria-[current=page]:underline'

const ITEMS: { to: string; key: LayoutKey; end?: boolean }[] = [
  { to: '/', key: 'navHome', end: true },
  { to: '/schemes', key: 'navExplore' },
  { to: '/policy', key: 'navPolicy' },
  { to: '/ask', key: 'navAsk' },
  { to: '/profile', key: 'navProfile' },
]

export function AppLayout() {
  const { language } = useLanguage()
  const t = useMemo(() => translator(language), [language])
  const [open, setOpen] = useState(false)
  const online = useOnlineStatus()

  // Choosing a page closes the menu on a phone.
  const links = ITEMS.map((item) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.end}
      className={navLink}
      onClick={() => setOpen(false)}
    >
      {t(item.key)}
    </NavLink>
  ))

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-10 focus:rounded-lg focus:bg-brand focus:px-4 focus:py-3 focus:text-white"
      >
        {t('skip')}
      </a>

      {/* <output> is a polite status region: announced when the connection goes, removed when it returns. */}
      {!online && (
        <output
          lang={language}
          className="block border-b border-warn-line bg-warn-surface px-4 py-3 text-warn"
        >
          <span className="mx-auto block w-full max-w-6xl">
            <strong>{t('offlineTitle')}</strong> {t('offlineText')}
          </span>
        </output>
      )}

      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2">
          <Link to="/" className="inline-flex min-h-12 items-center gap-2 text-lg font-semibold">
            <img src="/favicon.svg" alt="" width={32} height={32} />
            CivicSaathi
          </Link>

          <div className="flex items-center gap-x-2">
            {/* On a wide screen the links sit in the bar; on a phone they open from the button. */}
            <nav aria-label={t('mainNav')} className="hidden flex-wrap lg:flex">
              {links}
            </nav>
            <LanguageSwitch
              label={t('languageGroup')}
              names={{ en: t('english'), bn: t('bengali'), hi: t('hindi') }}
            />
            <button
              type="button"
              aria-expanded={open}
              aria-controls="mobile-nav"
              onClick={() => setOpen((was) => !was)}
              className="inline-flex min-h-12 items-center gap-2 rounded-xl border border-muted px-3 font-medium lg:hidden"
            >
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                width="22"
                height="22"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              >
                <path d={open ? 'M6 6l12 12M18 6 6 18' : 'M4 7h16M4 12h16M4 17h16'} />
              </svg>
              {open ? t('closeMenu') : t('menu')}
            </button>
          </div>

          {open && (
            <nav
              id="mobile-nav"
              aria-label={t('mainNav')}
              className="flex w-full flex-col border-t border-line py-2 lg:hidden"
            >
              {links}
            </nav>
          )}
        </div>
      </header>

      {/* tabIndex lets the skip link move keyboard focus here. */}
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <footer lang={language} className="border-t border-line bg-surface">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-4 px-4 py-2 text-sm text-muted">
          <p className="py-2">{t('footer')}</p>
          <Link to="/status" className="inline-flex min-h-12 items-center text-brand underline">
            {t('status')}
          </Link>
        </div>
      </footer>
    </div>
  )
}
