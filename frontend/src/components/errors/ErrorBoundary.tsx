import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** What to show instead of the children once one of them has thrown while rendering. */
  fallback: (error: Error, reset: () => void) => ReactNode
  /** When this changes, the boundary tries its children again (for example a new address). */
  resetKey?: unknown
}

interface State {
  error: Error | null
  resetKey: unknown
}

/**
 * Keeps a crash in one part of the page from taking the rest down with it. React unmounts the
 * whole tree when a component throws while rendering and nothing catches it; this catches it, so
 * the header, the navigation and the other sections stay, and the broken part says so and can be
 * tried again. It does not catch errors in event handlers or in promises: those are handled where
 * they happen (see `apiFetch`, which turns every failure into an `ApiError`).
 *
 * It knows nothing about the router, so it also works around a part of a page that is not a route.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, resetKey: this.props.resetKey }

  static getDerivedStateFromError(error: unknown): Partial<State> {
    return { error: error instanceof Error ? error : new Error(String(error)) }
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    return props.resetKey === state.resetKey ? null : { error: null, resetKey: props.resetKey }
  }

  private reset = () => this.setState({ error: null })

  render() {
    const { error } = this.state
    return error ? this.props.fallback(error, this.reset) : this.props.children
  }
}
