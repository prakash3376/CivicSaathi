import { useLocation, useNavigate, useRouteError } from 'react-router'
import { ErrorPanel } from './ErrorPanel'
import { isChunkLoadError } from './isChunkLoadError'
import { reloadPage } from './reload'

/**
 * The `errorElement` of the routes: shown when a page throws while rendering, or when its code
 * could not be fetched (the visitor is offline, or the site was updated since the page loaded).
 * Never an empty screen. "Try again" reloads for a failed fetch (the browser would remember the
 * failure otherwise) and for anything else goes to the same address again, which makes the router
 * render the page afresh. `standalone` is for a failure of the page frame itself, which has no
 * header around it to keep.
 */
export function RouteError({ standalone = false }: { standalone?: boolean }) {
  const error = useRouteError()
  const location = useLocation()
  const navigate = useNavigate()

  const retry = () =>
    isChunkLoadError(error) ? reloadPage() : void navigate(location, { replace: true })

  const panel = <ErrorPanel scope="page" error={error} onRetry={retry} />
  return standalone ? <div className="mx-auto w-full max-w-3xl p-4 py-12">{panel}</div> : panel
}
