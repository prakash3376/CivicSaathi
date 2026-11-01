import type { SectorId } from '@/api/types'
import { searchWords } from './searchSchemes'
import { SECTOR_IDS } from './sectors'
import type { Translate } from './strings'
import { sectorText, sectorTitle } from './useSectorText'

/** The sectors whose name or description contain every word typed. */
export function matchingSectors(t: Translate, text: string): SectorId[] {
  const wanted = searchWords(text)
  if (wanted.length === 0) return []
  return SECTOR_IDS.filter((id) => {
    const hay = `${sectorTitle(t, id)} ${sectorText(t, id)}`.toLocaleLowerCase()
    return wanted.every((word) => hay.includes(word))
  })
}
