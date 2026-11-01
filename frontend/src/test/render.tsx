import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { createRoutes, type Resolve } from '@/app/router'
import { LanguageProvider } from '@/i18n/LanguageProvider'
import { AdminPage } from '@/pages/AdminPage'
import { ChatPage } from '@/pages/ChatPage'
import { EligibilityPage } from '@/pages/EligibilityPage'
import { PolicyPage } from '@/pages/PolicyPage'
import { ProfilePage } from '@/pages/ProfilePage'
import { SchemeDetailsPage } from '@/pages/SchemeDetailsPage'
import { SchemesPage } from '@/pages/SchemesPage'
import { SearchPage } from '@/pages/SearchPage'
import { SectorPage } from '@/pages/SectorPage'
import { StatusPage } from '@/pages/StatusPage'
import { createTestQueryClient } from './utils'

/** The pages as components, so that a test sees a page the moment it renders. */
const EAGER = {
  SchemesPage,
  SchemeDetailsPage,
  EligibilityPage,
  SectorPage,
  SearchPage,
  PolicyPage,
  ProfilePage,
  ChatPage,
  StatusPage,
  AdminPage,
} satisfies Record<Parameters<Resolve>[0], () => React.JSX.Element>

const eagerly: Resolve = (name) => ({ Component: EAGER[name] })

function mount(routes: RouteObject[], path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const view = render(
    <QueryClientProvider client={createTestQueryClient()}>
      <LanguageProvider>
        <RouterProvider router={router} />
      </LanguageProvider>
    </QueryClientProvider>,
  )
  return { ...view, router }
}

/** The whole application (layout, language, routes) at an address, as a visitor would meet it. */
export function renderAt(path: string) {
  return mount(createRoutes(eagerly), path)
}

/** The application with its real, lazily loaded routes: a page appears once its module has loaded. */
export function renderLazilyAt(path: string) {
  return mount(createRoutes(), path)
}

/** The real frame and error handling around pages of the test's own making (to make one fail). */
export function renderWithPages(resolve: Resolve, path: string) {
  return mount(createRoutes(resolve), path)
}
