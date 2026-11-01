/**
 * Reload the page. It is its own function so that a test can replace it: jsdom cannot reload.
 * Used when a page's code could not be fetched: a failed module import is remembered by the
 * browser until the page is loaded again, so trying the same import again would fail the same way.
 */
export function reloadPage(): void {
  window.location.reload()
}
