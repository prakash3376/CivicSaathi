/**
 * Whether an error is the browser failing to fetch a page's code (the visitor went offline after
 * the page loaded, or the site was updated and the old file is gone), as opposed to a bug in the
 * code that did load. The two are told apart by the browsers' own wording.
 */
const CHUNK_FAILURE =
  /dynamically imported module|importing a module script failed|error loading dynamically imported|failed to fetch dynamically|chunkloaderror|loading chunk .* failed|loading css chunk/i

export function isChunkLoadError(error: unknown): boolean {
  if (error instanceof Error) {
    return error.name === 'ChunkLoadError' || CHUNK_FAILURE.test(error.message)
  }
  return typeof error === 'string' && CHUNK_FAILURE.test(error)
}
