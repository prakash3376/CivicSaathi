import type { BudgetRecord, SchemeSummary } from '@/api/types'
import { SectorCard } from './SectorCard'
import { budgetOf, inSector } from './sectorSources'
import { SECTOR_IDS } from './sectors'
import type { Translate } from './strings'

/**
 * All twelve sectors in a responsive grid. `schemes` and `budget` only decide the counts (none are
 * shown until the schemes have loaded; a budget that has not loaded counts as none).
 */
export function SectorGrid({
  schemes,
  budget,
  t,
}: {
  schemes: readonly SchemeSummary[] | undefined
  budget?: readonly BudgetRecord[] | undefined
  t: Translate
}) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {SECTOR_IDS.map((id) => (
        <SectorCard
          key={id}
          id={id}
          t={t}
          count={schemes ? inSector(schemes, id).length : null}
          records={budget ? budgetOf(budget, id).length : 0}
        />
      ))}
    </ul>
  )
}
