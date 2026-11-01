import { Link } from 'react-router'
import type { SectorId } from '@/api/types'
import { SectorIcon } from './SectorIcon'
import { sectorText, sectorTitle } from './useSectorText'
import type { Translate } from './strings'

/**
 * One sector as a card: its picture, name, what it covers, and how many verified schemes it has
 * (said in words, so an empty sector is honest about it).
 */
export function SectorCard({
  id,
  count,
  records = 0,
  t,
}: {
  id: SectorId
  count: number | null
  /** Budget records of the sector, counted apart from schemes. */
  records?: number
  t: Translate
}) {
  const has = (count ?? 0) + records > 0
  const counts = [
    count === 1
      ? t('schemeCountOne')
      : count && count > 1
        ? t('schemeCountMany', { n: count })
        : '',
    records === 1 ? t('budgetOne') : records > 1 ? t('budgetShown', { n: records }) : '',
  ].filter(Boolean)
  return (
    <li>
      <Link
        to={`/sectors/${id}`}
        className="group flex h-full flex-col gap-3 rounded-2xl border border-line bg-surface p-5 hover:bg-brand-soft"
      >
        <span className="grid size-12 place-items-center rounded-xl bg-brand-soft text-brand group-hover:bg-surface">
          <SectorIcon id={id} />
        </span>
        <span className="block space-y-1">
          <span className="block text-lg font-semibold">{sectorTitle(t, id)}</span>
          <span className="block text-muted">{sectorText(t, id)}</span>
        </span>
        <span className="mt-auto flex items-center justify-between gap-2 pt-1 text-sm">
          <span className={has ? 'font-medium text-ok' : 'text-muted'}>
            {count === null ? '' : has ? counts.join(' \u{B7} ') : t('schemeCountNone')}
          </span>
          <span className="font-medium text-brand underline underline-offset-4">
            {t('openSector')}
            <span className="sr-only">: {sectorTitle(t, id)}</span>
          </span>
        </span>
      </Link>
    </li>
  )
}
