import { useCallback, useEffect, useRef, useState } from 'react'
import { askQuestion } from '@/api/assistant'
import type { Answer, AskRequest } from '@/api/types'

export type TurnState =
  { status: 'pending' } | { status: 'done'; answer: Answer } | { status: 'error'; error: Error }

/** One question and what became of it. */
export interface Turn {
  id: number
  request: AskRequest
  state: TurnState
}

const HISTORY = 3 // earlier questions sent along with a question

/**
 * A conversation: each question with its answer, in order. It lives in memory only, so it is gone
 * when the page is closed; no question or answer is stored (SPEC AC9). One question is asked at
 * a time, and any still waiting is cancelled when the page is left.
 */
export function useChat() {
  const [turns, setTurns] = useState<Turn[]>([])
  const nextId = useRef(1)
  const waiting = useRef(new Set<AbortController>())
  const asked = useRef<{ id: number; question: string }[]>([])

  useEffect(() => {
    const controllers = waiting.current
    return () => {
      for (const controller of controllers) controller.abort()
    }
  }, [])

  const run = useCallback(async (id: number, request: AskRequest): Promise<TurnState | null> => {
    const controller = new AbortController()
    waiting.current.add(controller)
    const settle = (state: TurnState) =>
      setTurns((all) => all.map((turn) => (turn.id === id ? { ...turn, state } : turn)))
    // The questions before this one help to find the evidence for a follow-up. They are sent
    // with the request and never stored anywhere but here.
    const history = asked.current
      .filter((item) => item.id < id)
      .slice(-HISTORY)
      .map((item) => item.question)
    try {
      const answer = await askQuestion(
        history.length > 0 ? { ...request, history } : request,
        controller.signal,
      )
      // An answer that arrives after the page was left or the chat cleared belongs to nothing.
      if (controller.signal.aborted) return null
      const state: TurnState = { status: 'done', answer }
      settle(state)
      return state
    } catch (error) {
      if (controller.signal.aborted) return null // the page was left or the chat cleared
      const state: TurnState = {
        status: 'error',
        error: error instanceof Error ? error : new Error(String(error)),
      }
      settle(state)
      return state
    } finally {
      waiting.current.delete(controller)
    }
  }, [])

  const ask = useCallback(
    /** Asks, and tells how the question ended (null if it was cancelled). */
    (request: AskRequest): Promise<TurnState | null> => {
      const id = nextId.current++
      asked.current.push({ id, question: request.question })
      setTurns((all) => [...all, { id, request, state: { status: 'pending' } }])
      return run(id, request)
    },
    [run],
  )

  const retry = useCallback(
    (id: number) => {
      const turn = turns.find((candidate) => candidate.id === id)
      if (!turn) return
      setTurns((all) =>
        all.map((candidate) =>
          candidate.id === id ? { ...candidate, state: { status: 'pending' } } : candidate,
        ),
      )
      void run(id, turn.request)
    },
    [run, turns],
  )

  const clear = useCallback(() => {
    for (const controller of waiting.current) controller.abort()
    waiting.current.clear()
    asked.current = []
    setTurns([])
  }, [])

  const pending = turns.some((turn) => turn.state.status === 'pending')
  return { turns, ask, retry, clear, pending }
}
