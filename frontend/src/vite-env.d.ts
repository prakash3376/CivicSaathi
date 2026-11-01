interface ImportMetaEnv {
  /** Base URL of the CivicSaathi API as seen by the browser. Empty means "same origin". */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
