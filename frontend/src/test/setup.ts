import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// `findBy…` and `waitFor` give up after 1 s by default. A page that is slow to render because the
// machine is busy (22 test workers, a dev server running) is not a broken page, and no test asserts
// that something is quick, so wait long enough for a slow machine; a page that never renders still
// fails, only later.
configure({ asyncUtilTimeout: 10_000 })

afterEach(() => {
  cleanup()
})
