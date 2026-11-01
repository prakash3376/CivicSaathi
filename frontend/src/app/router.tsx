import type { ComponentType } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router'
import { RouteError } from '@/components/errors/RouteError'
import { AppLayout } from '@/components/layout/AppLayout'
import { LoadingFrame } from '@/components/layout/LoadingFrame'
import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'

/**
 * How each page other than the home page is fetched. The home page and the frame around every page
 * stay in the first download: that is what almost every visit needs. The assistant, the voice code,
 * the eligibility form and the admin page are the heavy parts, and a visitor who never opens them
 * never pays for them. The saving on the first page is modest, about 15% (docs/BENCHMARKS.md): the
 * shared code the home page needs is most of the download.
 */
export const PAGES = {
  SchemesPage: () => import('@/pages/SchemesPage').then((m) => m.SchemesPage),
  SchemeDetailsPage: () => import('@/pages/SchemeDetailsPage').then((m) => m.SchemeDetailsPage),
  EligibilityPage: () => import('@/pages/EligibilityPage').then((m) => m.EligibilityPage),
  SectorPage: () => import('@/pages/SectorPage').then((m) => m.SectorPage),
  SearchPage: () => import('@/pages/SearchPage').then((m) => m.SearchPage),
  PolicyPage: () => import('@/pages/PolicyPage').then((m) => m.PolicyPage),
  ProfilePage: () => import('@/pages/ProfilePage').then((m) => m.ProfilePage),
  ChatPage: () => import('@/pages/ChatPage').then((m) => m.ChatPage),
  StatusPage: () => import('@/pages/StatusPage').then((m) => m.StatusPage),
  AdminPage: () => import('@/pages/AdminPage').then((m) => m.AdminPage),
} satisfies Record<string, () => Promise<ComponentType>>

export type PageName = keyof typeof PAGES

/** What a route needs to show a page: a component now, or the means to load it. */
export type Resolve = (name: PageName) => Pick<RouteObject, 'Component' | 'lazy'>

/**
 * React Router's own mechanism: the page's module is loaded before the page renders, while the old
 * page stays on screen, so there is no flash of an empty layout.
 */
const lazily: Resolve = (name) => ({ lazy: async () => ({ Component: await PAGES[name]() }) })

/**
 * Every screen lives under the shared layout. Add new pages here and in `PAGES`. The tests call
 * this with pages already imported, so that they need not wait; the application loads them lazily.
 */
export function createRoutes(resolve: Resolve = lazily): RouteObject[] {
  return [
    {
      path: '/',
      element: <AppLayout />,
      // A failure of the frame itself (the header, the footer): nothing around it to keep.
      errorElement: <RouteError standalone />,
      // Shown on a first visit to a lazy page, until its code has arrived.
      HydrateFallback: LoadingFrame,
      children: [
        {
          // A page that throws, or whose code cannot be fetched, is replaced by an explanation
          // with a way to try again, inside the frame: the header and the menu stay usable.
          errorElement: <RouteError />,
          children: [
            { index: true, element: <HomePage /> },
            { path: 'schemes', ...resolve('SchemesPage') },
            { path: 'schemes/:schemeId', ...resolve('SchemeDetailsPage') },
            { path: 'schemes/:schemeId/check', ...resolve('EligibilityPage') },
            { path: 'sectors/:sectorId', ...resolve('SectorPage') },
            { path: 'search', ...resolve('SearchPage') },
            { path: 'policy', ...resolve('PolicyPage') },
            { path: 'profile', ...resolve('ProfilePage') },
            { path: 'ask', ...resolve('ChatPage') },
            { path: 'status', ...resolve('StatusPage') },
            { path: 'admin', ...resolve('AdminPage') },
            { path: '*', element: <NotFoundPage /> },
          ],
        },
      ],
    },
  ]
}

export const routes = createRoutes()

export const createAppRouter = () => createBrowserRouter(routes)
