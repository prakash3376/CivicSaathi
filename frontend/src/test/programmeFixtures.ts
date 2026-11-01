import type { BudgetRecord, ProgrammeDetails, SchemeSummary, SchemesResponse } from '@/api/types'
import { schemesBody } from './schemeFixtures'

const text = (en: string) => ({
  en,
  bn: `\u{09AC}\u{09BE}\u{0982}: ${en}`,
  hi: `\u{0939}\u{093F}: ${en}`,
})

const cite = (quote: string, where = 'page 2') => ({ source_id: 'demo-health-guide', quote, where })

/** Programmes that are read, not scored: no tracks, no deadline, no questionnaire. */
export const healthCover: SchemeSummary = {
  id: 'demo-health-cover',
  name: 'Demo Health Cover',
  authority: 'Department of Health Demos',
  level: 'state',
  state: 'West Bengal',
  sectors: ['health', 'social-welfare'],
  summary: text('Cover for hospital treatment.'),
  source_ids: ['demo-health-guide'],
  tracks: [],
  deadline: null,
  layout: 'info',
  kind: 'scheme',
  status: 'active',
  target: text('Families of the State.'),
  benefit: 'Cover of Rs. 5,00,000 per family per year.',
  last_verified: '2026-10-31',
}

export const roadWorks: SchemeSummary = {
  ...healthCover,
  id: 'demo-roads',
  name: 'Demo Rural Roads',
  authority: 'Ministry of Roads Demos',
  level: 'central',
  state: null,
  sectors: ['transport'],
  kind: 'infrastructure',
  benefit: 'All-weather roads to unconnected villages.',
  source_ids: ['demo-roads-guide'],
}

export const closedScheme: SchemeSummary = {
  ...healthCover,
  id: 'demo-closed',
  name: 'Demo Closed Scheme',
  sectors: ['employment'],
  status: 'closed',
  source_ids: ['demo-closed-guide'],
}

export const catalogueBody: SchemesResponse = {
  schemes: [...schemesBody.schemes, healthCover, roadWorks, closedScheme],
}

export const healthCoverDetails: ProgrammeDetails = {
  layout: 'info',
  id: healthCover.id,
  name: healthCover.name,
  kind: 'scheme',
  sectors: ['health', 'social-welfare'],
  authority: healthCover.authority,
  level: 'state',
  state: 'West Bengal',
  applicable_states: ['West Bengal'],
  status: 'active',
  status_note: '',
  summary: healthCover.summary,
  target: healthCover.target!,
  source_ids: ['demo-health-guide'],
  last_verified: '2026-10-31',
  published_on: '2026-04-28',
  effective_on: null,
  benefits: [
    {
      text: 'Cover of Rs. 5,00,000 per family per year.',
      evidence: [cite('Each family is covered up to Rs. 5,00,000 per year.', 'page 3')],
    },
  ],
  eligibility: [
    {
      text: 'Any family living in the State may enrol.',
      evidence: [cite('Any family that lives in the State may enrol for the cover.')],
    },
  ],
  exclusions: [
    {
      text: 'Serving government employees are not covered.',
      evidence: [cite('Serving government employees are not covered by this scheme.')],
    },
  ],
  documents: [
    {
      text: 'A ration card.',
      evidence: [cite('Enrolment needs a ration card of the family.')],
    },
  ],
  steps: [
    {
      text: 'Visit the nearest enrolment camp.',
      evidence: [cite('Families should visit the nearest enrolment camp.')],
    },
  ],
  apply: {
    label: 'Demo health portal',
    url: 'https://health.demo.gov.in',
    evidence: [cite('The portal of the scheme is open to every family.')],
  },
  not_stated: ['The last date to enrol.'],
  sources: [
    {
      id: 'demo-health-guide',
      title: 'Demo Health Cover: Guidelines',
      url: 'https://health.demo.gov.in/guide.pdf',
    },
  ],
}

const figure = (
  basis: BudgetRecord['figures'][number]['basis'],
  year: string,
  amount: number,
  quote: string,
) => ({
  basis,
  year,
  amount,
  unit: 'crore' as const,
  evidence: [{ source_id: 'demo-budget-doc', quote, where: 'page 12' }],
})

const source = {
  id: 'demo-budget-doc',
  title: 'Demo Budget at a Glance',
  url: 'https://budget.demo.gov.in/g.pdf',
}

/** An estimate only: a plan. */
export const healthBudget: BudgetRecord = {
  id: 'union-health',
  budget_year: '2026-27',
  level: 'central',
  state: null,
  sector: 'health',
  kind: 'allocation',
  title: 'Union Budget 2026-27: Health',
  department: 'Ministry of Health Demos',
  last_verified: '2026-10-31',
  summary: text('What is set aside for health.'),
  meaning: 'The plan for health is Rs. 1,28,650 crore.',
  figures: [figure('budget_estimate', '2026-27', 128650, 'Health 1,28,650 in the year 2026-27')],
  statements: [],
  sources: [source],
  not_actual_spending: true,
}

/** With a Revised Estimate and an Actual for earlier years. */
export const educationBudget: BudgetRecord = {
  ...healthBudget,
  id: 'wb-education',
  budget_year: '2026-27',
  level: 'state',
  state: 'West Bengal',
  sector: 'education',
  title: 'West Bengal Budget 2026-27: Education',
  department: 'Department of Education Demos',
  meaning: '',
  figures: [
    figure('budget_estimate', '2026-27', 41000, 'Education 41,000 in the year 2026-27'),
    figure('revised_estimate', '2025-26', 39000, 'Education 39,000 in the year 2025-26'),
    figure('actual', '2024-25', 37500, 'Education 37,500 in the year 2024-25'),
  ],
  not_actual_spending: false,
}

export const taxBudget: BudgetRecord = {
  ...healthBudget,
  id: 'union-tax',
  sector: null,
  kind: 'tax',
  title: 'Union Budget 2026-27: Taxation',
  meaning: '',
  figures: [],
  statements: [
    {
      text: 'The tax slabs are changed.',
      evidence: [
        {
          source_id: 'demo-budget-doc',
          quote: 'The tax slabs are changed as follows.',
          where: 'page 2',
        },
      ],
    },
  ],
  not_actual_spending: true,
}

export const budgetBody = { records: [healthBudget, educationBudget, taxBudget] }
