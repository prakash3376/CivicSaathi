import type { SectorId } from '@/api/types'

/** The twelve sectors, in the order the home page shows them. */
export const SECTOR_IDS: readonly SectorId[] = [
  'education',
  'health',
  'agriculture',
  'women-child',
  'employment',
  'housing',
  'social-welfare',
  'business',
  'transport',
  'budget',
  'environment',
  'public-services',
]

/** The part of a string key that names a sector (`educationTitle`, `womenChildTitle`, ...). */
export const SECTOR_KEY = {
  education: 'education',
  health: 'health',
  agriculture: 'agriculture',
  'women-child': 'womenChild',
  employment: 'employment',
  housing: 'housing',
  'social-welfare': 'socialWelfare',
  business: 'business',
  transport: 'transport',
  budget: 'budget',
  environment: 'environment',
  'public-services': 'publicServices',
} as const satisfies Record<SectorId, string>

export type SectorKey = (typeof SECTOR_KEY)[SectorId]

export function isSectorId(value: string | undefined): value is SectorId {
  return SECTOR_IDS.some((id) => id === value)
}

/** The drawing of each sector: SVG paths on a 24 x 24 grid, drawn as outlines. */
export const SECTOR_ICON: Record<SectorId, string[]> = {
  education: ['M22 10 12 5 2 10l10 5 10-5Z', 'M6 12v5c3 2 9 2 12 0v-5'],
  health: [
    'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8Z',
  ],
  agriculture: ['M12 22v-9', 'M12 13c0-4 3-7 8-7 0 5-3 7-8 7Z', 'M12 15c0-3-2-5-6-5 0 4 2 5 6 5Z'],
  'women-child': [
    'M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
    'M3 20v-1a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v1',
    'M17 11a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
    'M21 20v-.5a4 4 0 0 0-3-3.9',
  ],
  employment: [
    'M4 7h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1Z',
    'M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2',
    'M3 13h18',
  ],
  housing: ['M3 11 12 3l9 8', 'M5 10v10h14V10', 'M10 20v-6h4v6'],
  'social-welfare': ['M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3Z', 'M12 9v6M9 12h6'],
  business: [
    'M3 9l1-5h16l1 5',
    'M4 9v11h16V9',
    'M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0',
    'M10 20v-5h4v5',
  ],
  transport: [
    'M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12H4V5Z',
    'M4 11h16',
    'M7 17v3M17 17v3',
    'M8 14h.01M16 14h.01',
  ],
  budget: ['M3 3v18h18', 'M7 15v3M12 9v9M17 12v6'],
  environment: [
    'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
    'M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  ],
  'public-services': ['M3 21h18', 'M5 21V10M9 21V10M15 21V10M19 21V10', 'M2 10 12 3l10 7H2Z'],
}
