/** True for an address a link may point to: a web page, never `javascript:` or `data:`. */
export function isWebAddress(address: string): boolean {
  try {
    const { protocol } = new URL(address)
    return protocol === 'https:' || protocol === 'http:'
  } catch {
    return false // not an absolute address at all
  }
}
