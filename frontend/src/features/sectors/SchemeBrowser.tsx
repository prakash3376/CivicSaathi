import { useId, useMemo, useState, type ReactNode } from 'react'
import type { SchemeSummary } from '@/api/types'
import { secondaryButton } from '@/components/ui/buttonStyles'
import { SchemeCard } from '@/features/schemes/SchemeCard'
import type { Translate as SchemeTranslate } from '@/features/schemes/strings'
import {
  filterSchemes,
  NO_FILTERS,
  statesOf,
  type LevelFilter,
  type SchemeFilters,
} from './searchSchemes'
import type { Translate } from './strings'

const control = 'min-h-12 w-full rounded-xl border border-muted bg-surface px-3 text-ink'

interface Props {
  schemes: readonly SchemeSummary[]
  t: Translate
  schemeT: SchemeTranslate
  /** What to show when there is no scheme at all (not when the filters hide them all). */
  empty: ReactNode
}

/**
 * Search, the Central/State filter and the state filter over a list of schemes, and the schemes
 * that pass. The same component serves the explorer (every scheme) and each sector (its own).
 */
export function SchemeBrowser({ schemes, t, schemeT, empty }: Props) {
  const ids = useId()
  const [filters, setFilters] = useState<SchemeFilters>(NO_FILTERS)
  const shown = useMemo(
    () => filterSchemes(schemes, filters, t.language),
    [schemes, filters, t.language],
  )
  const states = useMemo(() => statesOf(schemes), [schemes])

  if (schemes.length === 0) return <>{empty}</>

  const set = (change: Partial<SchemeFilters>) => setFilters((old) => ({ ...old, ...change }))
  const filtered = filters.text.trim() !== '' || filters.level !== 'all' || filters.state !== ''

  return (
    <div className="space-y-5">
      <search>
        <form onSubmit={(event) => event.preventDefault()} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor={`${ids}-text`} className="block font-medium">
              {t('searchLabel')}
            </label>
            <input
              id={`${ids}-text`}
              type="search"
              value={filters.text}
              onChange={(event) => set({ text: event.target.value })}
              placeholder={t('searchPlaceholder')}
              className={control}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor={`${ids}-level`} className="block font-medium">
                {t('levelLabel')}
              </label>
              <select
                id={`${ids}-level`}
                value={filters.level}
                onChange={(event) => set({ level: event.target.value as LevelFilter })}
                className={control}
              >
                <option value="all">{t('levelAll')}</option>
                <option value="central">{t('levelCentral')}</option>
                <option value="state">{t('levelState')}</option>
              </select>
            </div>
            {states.length > 0 && (
              <div className="space-y-2">
                <label htmlFor={`${ids}-state`} className="block font-medium">
                  {t('stateLabel')}
                </label>
                <select
                  id={`${ids}-state`}
                  value={filters.state}
                  onChange={(event) => set({ state: event.target.value })}
                  className={control}
                >
                  <option value="">{t('stateAll')}</option>
                  {states.map((state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </form>
      </search>

      {/* A polite live region: the count changes as the person types or filters. */}
      <output className="block text-muted">
        {shown.length === 1 ? t('shownOne') : t('shownMany', { n: shown.length })}
      </output>

      {shown.length > 0 ? (
        <ul className="grid gap-4 md:grid-cols-2">
          {shown.map((scheme) => (
            <SchemeCard key={scheme.id} scheme={scheme} t={schemeT} />
          ))}
        </ul>
      ) : (
        <div className="space-y-3 rounded-2xl border border-line bg-surface p-5">
          <p>{t('noMatch')}</p>
          {filtered && (
            <button
              type="button"
              onClick={() => setFilters(NO_FILTERS)}
              className={secondaryButton}
            >
              {t('clearFilters')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
