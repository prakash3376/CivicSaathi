/** Typed access to build-time environment variables. Read them here, nowhere else. */
export const env = {
  /** No trailing slash. Empty when the API is on the same origin (dev proxy or reverse proxy). */
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, ''),
} as const
