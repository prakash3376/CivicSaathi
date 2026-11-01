import { useMemo } from 'react'
import type { SectorId } from '@/api/types'
import { useLanguage } from '@/i18n/LanguageContext'
import { SECTOR_KEY } from './sectors'
import { translator, type SectorStringKey, type Translate } from './strings'

/** The interface language and the sector words in it. */
export function useSectorText() {
  const { language } = useLanguage()
  const t = useMemo(() => translator(language), [language])
  return { language, t }
}

/** The name of a sector, in the language of `t`. */
export function sectorTitle(t: Translate, id: SectorId): string {
  return t(`${SECTOR_KEY[id]}Title` satisfies SectorStringKey)
}

/** What a sector covers, in the language of `t`. */
export function sectorText(t: Translate, id: SectorId): string {
  return t(`${SECTOR_KEY[id]}Text` satisfies SectorStringKey)
}
