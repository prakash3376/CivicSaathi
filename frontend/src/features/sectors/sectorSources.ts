import type { BudgetRecord, SchemeSummary, SectorId } from '@/api/types'
import { SECTOR_IDS } from './sectors'

/** The schemes, programmes and services listed under a sector (one may be listed under several). */
export function inSector(schemes: readonly SchemeSummary[], id: SectorId): SchemeSummary[] {
  return schemes.filter((scheme) => scheme.sectors.includes(id))
}

/**
 * The budget records that belong on a sector's page: its own allocations, and, for the Budget
 * sector, every record (including taxation and whole-budget ones that have no sector).
 */
export function budgetOf(records: readonly BudgetRecord[], id: SectorId): BudgetRecord[] {
  return id === 'budget' ? [...records] : records.filter((record) => record.sector === id)
}

/**
 * Every official document a question about the sector may be answered from: those behind its
 * programmes and behind its budget records. This is the scope handed to AI Saathi.
 */
export function sourceIdsOf(
  id: SectorId,
  schemes: readonly SchemeSummary[],
  records: readonly BudgetRecord[],
): string[] {
  const ids = new Set<string>()
  for (const scheme of inSector(schemes, id)) scheme.source_ids.forEach((s) => ids.add(s))
  for (const record of budgetOf(records, id)) record.sources.forEach((s) => ids.add(s.id))
  return [...ids]
}

/**
 * A few schemes to feature: one from each sector in turn (the first running one that is not
 * already chosen), then another round if more are wanted, so that the home page shows the breadth
 * and not six from the same sector.
 */
export function featuredSchemes(schemes: readonly SchemeSummary[], count: number): SchemeSummary[] {
  const chosen: SchemeSummary[] = []
  let added = true
  while (added && chosen.length < count) {
    added = false
    for (const sector of SECTOR_IDS) {
      const next = inSector(schemes, sector).find(
        (scheme) => scheme.status === 'active' && !chosen.includes(scheme),
      )
      if (next && chosen.length < count) {
        chosen.push(next)
        added = true
      }
    }
  }
  return chosen
}
