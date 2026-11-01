import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router/dom'
import { LanguageProvider } from '@/i18n/LanguageProvider'
import { createAppRouter } from './router'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      // Mobile data is precious: do not refetch just because the tab regained focus.
      refetchOnWindowFocus: false,
    },
  },
})

const router = createAppRouter()

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <RouterProvider router={router} />
      </LanguageProvider>
    </QueryClientProvider>
  )
}
