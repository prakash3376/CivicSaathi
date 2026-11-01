import type { BudgetFigure, BudgetRecord, FigureBasis } from '@/api/types'
import { OfficialLink } from '@/features/assistant/OfficialLink'
import { EvidenceQuote } from '@/features/schemes/EvidenceQuote'
import type { Translate as SchemeTranslate } from '@/features/schemes/strings'
import { local } from '@/i18n/translator'
import type { SectorStringKey, Translate } from './strings'

const BASIS: Record<FigureBasis, SectorStringKey> = {
  budget_estimate: 'basisBudget',
  revised_estimate: 'basisRevised',
  actual: 'basisActual',
}

const KIND: Record<BudgetRecord['kind'], SectorStringKey> = {
  allocation: 'budgetKindAllocation',
  announcement: 'budgetKindAnnouncement',
  tax: 'budgetKindTax',
}

// Indian digit grouping (1,28,650), and always the digits 0-9.
const group = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })

function amountText(figure: BudgetFigure, t: Translate): string {
  const number = group.format(figure.amount)
  if (figure.unit === 'percent') return `${number} ${t('unitPercent')}`
  const unit = figure.unit === 'lakh_crore' ? t('unitLakhCrore') : t('unitCrore')
  return `\u{20B9}${number} ${unit}`
}

/**
 * What the budget documents say, as records: each figure with its financial year and whether it is
 * a Budget Estimate, a Revised Estimate or an Actual, and the words of the document behind it. A
 * record with no Actual figure says that its money is a plan, not money already spent.
 */
export function BudgetSection({
  records,
  t,
  schemeT,
}: {
  records: readonly BudgetRecord[]
  t: Translate
  schemeT: SchemeTranslate
}) {
  return (
    <ul className="space-y-4">
      {records.map((record) => (
        <li key={record.id}>
          <article className="space-y-3 rounded-2xl border border-line bg-surface p-5">
            <p className="flex flex-wrap gap-2 text-sm font-medium">
              <span className="rounded-md bg-brand-soft px-2 py-0.5 text-brand">
                {t(KIND[record.kind])}
              </span>
              <span className="rounded-md bg-brand-soft px-2 py-0.5 text-brand">
                {t('budgetOf', { year: record.budget_year })}
              </span>
            </p>
            <h3 className="text-xl font-semibold">{record.title}</h3>
            <p className="text-sm text-muted">
              {record.department} ·{' '}
              {record.level === 'state' && record.state
                ? t('stateBudget', { state: record.state })
                : t('centralBudget')}
            </p>
            <p className="max-w-prose">{local(record.summary, t.language)}</p>

            {record.figures.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-semibold">{t('figuresHeading')}</h4>
                <ul className="space-y-2">
                  {record.figures.map((figure) => (
                    <li key={`${figure.basis}:${figure.year}`} className="space-y-1">
                      <p>
                        <strong>{amountText(figure, t)}</strong>
                        <span className="text-muted">
                          {' \u{B7} '}
                          {t(BASIS[figure.basis])}
                          {' \u{B7} '}
                          {figure.year}
                        </span>
                      </p>
                      <EvidenceQuote evidence={figure.evidence} t={schemeT} />
                    </li>
                  ))}
                </ul>
                {record.not_actual_spending && (
                  <p className="max-w-prose rounded-xl bg-warn-surface p-3 text-sm text-warn">
                    {t('planNote')}
                  </p>
                )}
              </div>
            )}

            {record.meaning && (
              <div className="space-y-1">
                <h4 className="font-semibold">{t('meaningHeading')}</h4>
                <p lang="en" className="max-w-prose">
                  {record.meaning}
                </p>
                {t.language !== 'en' && <p className="text-sm text-muted">{t('englishOnly')}</p>}
              </div>
            )}

            {record.statements.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-semibold">{t('announcementsHeading')}</h4>
                <ul className="list-disc space-y-3 pl-6">
                  {record.statements.map((statement) => (
                    <li key={statement.text} className="space-y-1">
                      <p lang="en" className="max-w-prose">
                        {statement.text}
                      </p>
                      <EvidenceQuote evidence={statement.evidence} t={schemeT} />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-sm text-muted">
              {record.sources.map((source, index) => (
                <span key={source.id}>
                  {index > 0 && ' \u{B7} '}
                  <OfficialLink
                    url={source.url}
                    title={source.title}
                    openLabel={schemeT('openDocument')}
                  />
                </span>
              ))}
            </p>
          </article>
        </li>
      ))}
    </ul>
  )
}
