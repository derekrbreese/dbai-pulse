import { useState, useEffect, useCallback } from 'react'

/**
 * Lightweight hash-based router.
 * Returns { route, params, navigate }.
 *
 * Routes: #/  #/search  #/trends  #/compare  #/roster  #/player/:id
 */
export default function useHashRouter() {
  const parse = (hash) => {
    const raw = hash.replace(/^#\/?/, '') || ''
    const [path, queryString] = raw.split('?')
    const segments = path.split('/').filter(Boolean)

    const params = {}
    if (queryString) {
      for (const [key, value] of new URLSearchParams(queryString)) {
        params[key] = value
      }
    }

    if (segments.length === 0) return { route: 'home', params }
    if (segments[0] === 'player' && segments[1]) {
      return { route: 'player', params: { ...params, id: segments[1] } }
    }
    return { route: segments[0], params }
  }

  const [state, setState] = useState(() => parse(window.location.hash))

  useEffect(() => {
    const handler = () => setState(parse(window.location.hash))
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  const navigate = useCallback((path) => {
    window.location.hash = path.startsWith('#') ? path : `#/${path}`
  }, [])

  return { route: state.route, params: state.params, navigate }
}
