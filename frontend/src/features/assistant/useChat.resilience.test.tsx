import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { answerBody, jsonResponse } from '@/test/utils'
import { useChat, type TurnState } from './useChat'

afterEach(() => vi.unstubAllGlobals())

/** A fetch that answers only when told to, and ignores being aborted (a reply already on its way). */
function heldFetch() {
  const waiting: (() => void)[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          waiting.push(() => resolve(jsonResponse(answerBody)))
        }),
    ),
  )
  return { release: () => waiting.forEach((release) => release()) }
}

describe('useChat', () => {
  it('tells the caller a question was cancelled (null) when its answer arrives after clear()', async () => {
    const server = heldFetch()
    const { result } = renderHook(() => useChat())
    let ended: Promise<TurnState | null> = Promise.resolve(null)

    act(() => {
      ended = result.current.ask({ question: 'Will be abandoned', language: 'auto' })
    })
    expect(result.current.pending).toBe(true)
    act(() => result.current.clear())
    await act(async () => {
      server.release()
      await ended
    })

    // The voice conversation moves on from this value: a late answer must not be spoken or shown.
    await expect(ended).resolves.toBeNull()
    expect(result.current.turns).toEqual([])
    expect(result.current.pending).toBe(false)
  })

  it('tells the caller a question was cancelled when the page is left before the answer', async () => {
    const server = heldFetch()
    const { result, unmount } = renderHook(() => useChat())
    let ended: Promise<TurnState | null> = Promise.resolve(null)
    act(() => {
      ended = result.current.ask({ question: 'Leaving', language: 'auto' })
    })

    unmount()
    server.release()

    await expect(ended).resolves.toBeNull()
  })

  it('ends a question with its answer, and an unanswered one is never left pending', async () => {
    const server = heldFetch()
    const { result } = renderHook(() => useChat())
    act(() => {
      void result.current.ask({ question: 'Answered', language: 'auto' })
    })

    await act(async () => server.release())

    await waitFor(() => expect(result.current.pending).toBe(false))
    expect(result.current.turns[0]?.state.status).toBe('done')
  })

  it('ends a failed question as an error, never as pending', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const { result } = renderHook(() => useChat())

    let ended: TurnState | null = null
    await act(async () => {
      ended = await result.current.ask({ question: 'Will fail', language: 'auto' })
    })

    expect(ended).toMatchObject({ status: 'error' })
    expect(result.current.pending).toBe(false)
    expect(result.current.turns[0]?.request.question).toBe('Will fail')
  })
})
