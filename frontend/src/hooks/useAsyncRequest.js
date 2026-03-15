import { useState, useRef, useCallback } from 'react'

/**
 * Shared hook for async requests with race condition prevention.
 * Both RosterView and WaiverWire independently implemented this pattern —
 * this hook extracts the common logic.
 *
 * @returns {{ execute, loading, error, setError }}
 */
export default function useAsyncRequest() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const activeTokenRef = useRef(0)

  const execute = useCallback(async (asyncFn) => {
    activeTokenRef.current += 1
    const token = activeTokenRef.current
    setLoading(true)
    setError(null)

    try {
      const result = await asyncFn(token)
      if (token !== activeTokenRef.current) return null
      return result
    } catch (err) {
      if (token !== activeTokenRef.current) return null
      setError(err.message)
      throw err
    } finally {
      if (token === activeTokenRef.current) {
        setLoading(false)
      }
    }
  }, [])

  return { execute, loading, error, setError }
}
